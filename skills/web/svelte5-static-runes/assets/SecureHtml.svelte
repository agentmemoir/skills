<script>
  // Drop-in replacement for a raw {@html rawContent} usage.
  // Requires: npm install dompurify
  import DOMPurify from 'dompurify';

  /**
   * @typedef {Object} Props
   * @property {string} html - untrusted/raw HTML to render
   * @property {string[]} [allowedTags] - allowlist of tags; defaults to a conservative rich-text set
   * @property {string[]} [allowedAttr] - allowlist of attributes
   */

  /** @type {Props} */
  let {
    html,
    allowedTags = ['b', 'i', 'em', 'strong', 'a', 'p', 'br', 'ul', 'ol', 'li', 'blockquote', 'code', 'pre'],
    allowedAttr = ['href', 'target', 'rel']
  } = $props();

  let sanitized = $derived(
    DOMPurify.sanitize(html ?? '', {
      ALLOWED_TAGS: allowedTags,
      ALLOWED_ATTR: allowedAttr
    })
  );
</script>

{@html sanitized}
