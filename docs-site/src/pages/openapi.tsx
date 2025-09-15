import React from 'react';
import Layout from '@theme/Layout';
import { RedocStandalone } from 'redoc';

export default function OpenAPIPage() {
  return (
    <Layout title="API Reference" description="PortPulse OpenAPI reference">
      <div style={{ minHeight: 'calc(100vh - 120px)' }}>
        <RedocStandalone
          specUrl="/openapi.json"
          options={{
            hideDownloadButton: false,
            expandResponses: '200,201',
            pathInMiddlePanel: true,
            theme: {
              colors: { primary: { main: '#0D9488' } },
              typography: { fontSize: '14px', lineHeight: '1.6' },
              sidebar: { width: '300px' },
            },
          }}
        />
      </div>
    </Layout>
  );
}