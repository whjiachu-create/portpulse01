import React, { useEffect } from 'react';
import Layout from '@theme/Layout';
import Head from '@docusaurus/Head';

export default function Home(): JSX.Element {
  // Client-side redirect to /openapi (Redoc page)
  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.location.replace('/openapi');
    }
  }, []);

  // SSR-safe fallback with meta refresh + link
  return (
    <Layout title="PortPulse API Docs">
      <Head>
        <meta httpEquiv="refresh" content="0; url=/openapi" />
      </Head>
      <main style={{padding:'4rem 0', textAlign:'center'}}>
        <p>Redirecting to <a href="/openapi">OpenAPI</a>…</p>
        <noscript>
          You are seeing this page because JavaScript is disabled. Please follow{' '}
          <a href="/openapi">/openapi</a>.
        </noscript>
      </main>
    </Layout>
  );
}
