// docs-site/sidebars.ts
import type { SidebarsConfig } from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docs: [
    'intro',
    {
      type: 'category',
      label: 'Guides',
      collapsed: false,
      items: [
        'Guides/quickstarts',
        'Guides/authentication',
        'Guides/errors',
        'Guides/rate-limits',
        'Guides/csv-etag',
        'Guides/field-dictionary',
        'Guides/methodology',
        'Guides/versioning',
        'Guides/postman',
        'Guides/insomnia',
      ],
    },
    {
      type: 'category',
      label: 'Operations',
      collapsed: false,
      items: ['Ops/sla-status'],
    },
    'changelog',
  ],
};

export default sidebars;