import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';

const config: Config = {
  title: 'PortPulse Docs',
  url: 'https://docs.useportpulse.com',
  baseUrl: '/',
  favicon: 'img/favicon.svg',
  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',
  i18n: { defaultLocale: 'en', locales: ['en'] },
  staticDirectories: ['static'],

  presets: [
    [
      'classic',
      {
        docs: { sidebarPath: require.resolve('./sidebars.ts') },
        blog: false,
        theme: { customCss: require.resolve('./src/css/custom.css') },
      },
    ],
  ],

  themeConfig: {
    navbar: {
      title: 'PortPulse',
      items: [
        { to: '/docs/intro', label: 'Docs', position: 'left' },
        // Use internal page instead of static JSON to avoid broken link checks
        { to: '/openapi', label: 'API Reference', position: 'left' },
        { to: '/docs/Ops/sla-status', label: 'Status & SLA', position: 'right' },
      ],
    },
    footer: {
      style: 'dark',
      copyright: `© ${new Date().getFullYear()} PortPulse.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  },
};

export default config;