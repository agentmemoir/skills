<script>
  let { title = 'Hello' } = $props();
  let count = $state(0);
  let doubled = $derived(count * 2);
</script>

<main>
  <h1>{title}</h1>
  <button onclick={() => count++}>count: {count} / {doubled}</button>
</main>

<style>
  main {
    font-family: system-ui, sans-serif;
    padding: 2rem;
  }
</style>
