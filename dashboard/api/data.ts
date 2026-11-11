// Vercel serverless proxy: GET /api/data?f=positions.json
// Reads data/<f> from the (private) paper-trader repo with a server-side token, so no secret
// ever reaches the browser. Only files under data/ with safe names can be requested.
//
// Env vars (Vercel → Project → Settings → Environment Variables):
//   GITHUB_TOKEN   fine-grained PAT, this repo only, Contents: Read-only
//   GITHUB_REPO    owner/name, e.g. arwat8/Kalshi-strat
//   GITHUB_BRANCH  branch the paper trader commits to (default: main)

const SAFE = /^(?:[A-Za-z0-9_-]+\/)*[A-Za-z0-9_.-]+\.(?:json|csv)$/;

export async function GET(request: Request): Promise<Response> {
  const f = new URL(request.url).searchParams.get('f') ?? '';
  if (!SAFE.test(f) || f.includes('..')) return json({ error: 'bad file' }, 400);

  const repo = process.env.GITHUB_REPO;
  const token = process.env.GITHUB_TOKEN;
  const branch = process.env.GITHUB_BRANCH || 'main';
  if (!repo || !token) return json({ error: 'GITHUB_REPO / GITHUB_TOKEN not set' }, 500);

  const url = `https://api.github.com/repos/${repo}/contents/data/${f}?ref=${encodeURIComponent(branch)}`;
  const r = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github.raw',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'fedstrip-dashboard',
    },
  });
  if (!r.ok) return json({ error: `github ${r.status}` }, r.status === 404 ? 404 : 502);

  return new Response(await r.text(), {
    status: 200,
    headers: {
      'Content-Type': f.endsWith('.csv') ? 'text/csv; charset=utf-8' : 'application/json; charset=utf-8',
      // edge-cache for a minute; serve stale while refreshing
      'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=300',
    },
  });
}

function json(body: unknown, status: number) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}
