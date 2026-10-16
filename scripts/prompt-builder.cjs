#!/usr/bin/env node

const fs = require('node:fs/promises')
const path = require('node:path')

/**
 * Helper to handle async string replacement.
 */
const replaceAsync = async (str, regex, asyncFn) => {
  const promises = []
  str.replace(regex, (match, ...args) => {
    promises.push(asyncFn(match, ...args))
    return match
  })
  const data = await Promise.all(promises)
  return str.replace(regex, () => data.shift())
}

/**
 * Parses option strings like "lines=1-10" or "extensions:js,ts"
 * @param {string} optionsStr - The raw options string from the regex.
 * @returns {object} - Key-value pairs of options.
 */
const parseOptions = (optionsStr) => {
  if (!optionsStr) return {}
  return optionsStr.split('|').reduce((acc, part) => {
    // Support both key=value and key:value delimiters
    const [key, value] = part.split(/[:=](.*)/s).map(s => s?.trim())
    if (key && value) {
      acc[key] = value
    }
    return acc
  }, {})
}

/**
 * Recursively finds files in a directory.
 * @param {string} dir - Directory to search.
 * @param {string[]} [extensions] - Optional list of extensions to include (e.g. ['js', 'ts']).
 * @returns {Promise<string[]>} - Array of absolute file paths.
 */
const getFilesRecursively = async (dir, extensions = null) => {
  let results = []
  let list

  try {
    list = await fs.readdir(dir, { withFileTypes: true })
  } catch (err) {
    console.warn(`[Warning] Skipped folder: ${dir} (${err.message})`)
    return []
  }

  const pending = list.map(async (dirent) => {
    const res = path.resolve(dir, dirent.name)
    
    // Ignore common non-content folders
    if (dirent.name.startsWith('.') || dirent.name === 'node_modules') return

    if (dirent.isDirectory()) {
      const subFiles = await getFilesRecursively(res, extensions)
      results = results.concat(subFiles)
    } else {
      if (extensions) {
        const ext = path.extname(res).substring(1) // remove dot
        if (!extensions.includes(ext)) return
      }
      results.push(res)
    }
  })

  await Promise.all(pending)
  // Sort results to ensure deterministic output order
  return results.sort()
}

/**
 * Formats file content into the output structure.
 * @param {string} filePath - Absolute path to file.
 * @param {string} content - File content.
 * @returns {string} - Formatted string.
 */
const formatFileBlock = (filePath, content) => {
  // Calculate relative path for display
  const relPath = path.relative(process.cwd(), filePath)
  const ext = path.extname(filePath).substring(1) || 'text'
  return `File Path: \`${relPath}\`\n\n\`\`\`\`\`\`\`\`\`\`${ext}\n${content}\n\`\`\`\`\`\`\`\`\`\``
}

/**
 * Reads a file, applies line filtering if requested.
 * @param {string} filePath - Absolute path.
 * @param {object} options - Parsed options (lines, etc).
 * @returns {Promise<string>} - The processed content.
 */
const readFileContent = async (filePath, options) => {
  try {
    let content = await fs.readFile(filePath, 'utf8')

    // Handle Line Ranges (lines=1-5)
    if (options.lines) {
      const [startLine, endLine] = options.lines.split('-')
      const lines = content.split(/\r?\n/)
      const start = parseInt(startLine, 10) - 1
      const end = parseInt(endLine, 10)

      if (start < 0 || start >= lines.length) {
        console.warn(`[Warning] Line range ${options.lines} out of bounds for ${filePath}`)
      }
      content = lines.slice(start, end).join('\n')
    }

    return content
  } catch (err) {
    console.error(`[Error] Could not read file: ${filePath}`)
    return `[ERROR: File not found ${path.basename(filePath)}]`
  }
}

/**
 * Recursively processes content, resolving all paths relative to CWD.
 * @param {string} content - The text content to process.
 * @returns {Promise<string>} - The processed content.
 */
const processContent = async (content) => {
  // Regex Breakdown:
  // {{\s*              -> Start tag
  // (file|raw|folder)  -> Type (Group 1)
  // :                  -> Separator
  // ([^}|]+)           -> Path (Group 2)
  // (?:\|([^}]+))?     -> Optional Arguments starting with | (Group 3)
  // \s*}}              -> End tag
  const placeholderRegex = /{{\s*(file|raw|folder):([^}|]+)(?:\|([^}]+))?\s*}}/g

  return await replaceAsync(content, placeholderRegex, async (match, type, relPath, optionsStr) => {
    const targetPath = path.resolve(process.cwd(), relPath.trim())
    const options = parseOptions(optionsStr)

    if (type === 'folder') {
      // 1. Parse extensions if provided (extensions:js,ts)
      let allowedExts = null
      if (options.extensions) {
        allowedExts = options.extensions.split(',').map(e => e.trim())
      }

      // 2. Get all files recursively
      const files = await getFilesRecursively(targetPath, allowedExts)

      if (files.length === 0) {
        return `[Warning: No files found in ${relPath.trim()}]`
      }

      // 3. Read all files in parallel
      const filePromises = files.map(async (file) => {
        const fileContent = await readFileContent(file, {}) // No line options for bulk folder
        return formatFileBlock(file, fileContent)
      })

      const processedFiles = await Promise.all(filePromises)
      
      // 4. Join them
      return processedFiles.join('\n\n')

    } else {
      // Handle Single Files ('file' or 'raw')
      let fileContent = await readFileContent(targetPath, options)

      if (type === 'raw') {
        // Recurse: Process placeholders inside the imported raw file
        return await processContent(fileContent)
      } else {
        // Standard: Wrap in code block
        return formatFileBlock(targetPath, fileContent)
      }
    }
  })
}

const printHelp = () => {
  console.log(`
PromptBuild (CWD Mode)

Usage:
  node prompt-builder.js <inputFile> [outputFile]

Syntax:
  {{file:./path/to/script.js|lines=1-10}}
  {{raw:./path/to/template.md}}
  {{folder:./src/components|extensions:js,ts}}

Notes:
  - All file paths are relative to the CURRENT DIRECTORY.
  - Folders are scanned recursively.
`)
}

const main = async () => {
  const args = process.argv.slice(2)

  if (args.length === 0 || args.includes('--help') || args.includes('-h')) {
    printHelp()
    process.exit(0)
  }

  const inputPath = path.resolve(process.cwd(), args[0])
  let outputPath

  if (args[1]) {
    outputPath = path.resolve(process.cwd(), args[1])
  } else {
    const ext = path.extname(inputPath)
    const name = path.basename(inputPath, ext)
    const dir = path.dirname(inputPath)
    outputPath = path.resolve(dir, `.${name}.processed${ext}`)
  }

  try {
    console.log(`Reading input: ${inputPath}`)
    const initialContent = await fs.readFile(inputPath, 'utf8')

    console.log('Processing placeholders...')
    const finalContent = await processContent(initialContent)

    await fs.writeFile(outputPath, finalContent, 'utf8')
    console.log(`Success! Output written to: ${outputPath}`)
  } catch (err) {
    console.error(`Fatal Error: ${err.message}`)
    process.exit(1)
  }
}

main()