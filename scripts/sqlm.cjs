#!/usr/bin/env node

const fs = require('fs')
const fsp = require('fs/promises')
const path = require('path')

/**
 * Recursively scans a directory for SQL files.
 * @param {string} dir - The directory to scan.
 * @returns {Promise<string[]>} - A list of absolute file paths.
 */
async function scanDirectory(dir) {
  let results = []

  // Check if directory exists
  try {
    await fsp.access(dir)
  } catch {
    throw new Error(`Directory not found: ${dir}`)
  }

  const entries = await fsp.readdir(dir, { withFileTypes: true })

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name)

    if (entry.isDirectory()) {
      const subDirFiles = await scanDirectory(fullPath)
      results = results.concat(subDirFiles)
    } else if (entry.isFile() && path.extname(entry.name).toLowerCase() === '.sql') {
      results.push(fullPath)
    }
  }

  return results
}

/**
 * Appends a file's content to the output stream with a comment header.
 * @param {string} inputPath - Absolute path to input file.
 * @param {fs.WriteStream} writeStream - The stream to write to.
 */
async function appendFileToStream(inputPath, writeStream) {
  // create relative path for the comment (e.g. ./db/foo.sql)
  const relativePath = path.relative(process.cwd(), inputPath)
  const normalizedPath = relativePath.split(path.sep).join('/')
  const header = `-- File: ${normalizedPath}\n`

  // Write header
  if (!writeStream.write(header)) {
    await new Promise(resolve => writeStream.once('drain', resolve))
  }

  // Pipe file content
  const readStream = fs.createReadStream(inputPath, { encoding: 'utf8' })

  // Use pipeline to manage flow and errors automatically, but keep stream open
  // We cannot use strict pipeline here because it closes the destination.
  // Instead, we manually pipe and await the 'end' event.
  await new Promise((resolve, reject) => {
    readStream.on('data', (chunk) => {
      if (!writeStream.write(chunk)) {
        readStream.pause()
        writeStream.once('drain', () => readStream.resume())
      }
    })

    readStream.on('end', () => {
      // Add spacing between files
      writeStream.write('\n\n')
      resolve()
    })

    readStream.on('error', reject)
  })
}

async function main() {
  const args = process.argv.slice(2)

  if (args.length === 0) {
    console.error('Usage: node sqlm.js <input_directory> [output_file]')
    process.exit(1)
  }

  const inputDir = path.resolve(args[0])
  let outputPath

  // Determine output path
  if (args[1]) {
    outputPath = path.resolve(args[1])
  } else {
    // Strip trailing slashes for clean naming
    const cleanInput = args[0].replace(/[\\/]+$/, '')
    outputPath = path.resolve(`${cleanInput}.sql`)
  }

  // Ensure output directory exists
  const outputDir = path.dirname(outputPath)
  await fsp.mkdir(outputDir, { recursive: true })

  console.info(`Scanning: ${args[0]} ...`)

  try {
    const files = await scanDirectory(inputDir)

    if (files.length === 0) {
      console.info('No .sql files found.')
      return
    }

    // Sort files to ensure deterministic output (alphabetical order)
    files.sort((a, b) => a.localeCompare(b))

    const writeStream = fs.createWriteStream(outputPath)

    console.info(`Merging ${files.length} files...`)

    for (const file of files) {
      // Prevent self-inclusion if output file is inside input dir
      if (file === outputPath) continue

      await appendFileToStream(file, writeStream)
    }

    writeStream.end()

    await new Promise((resolve, reject) => {
      writeStream.on('finish', resolve)
      writeStream.on('error', reject)
    })

    console.info(`\nSuccess! Created: ${path.relative(process.cwd(), outputPath)}`)
  } catch (error) {
    console.error('\nError:', error.message)
    process.exit(1)
  }
}

main().catch(console.error)
