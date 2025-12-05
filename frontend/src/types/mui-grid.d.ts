/**
 * Type declaration fix for MUI v7 Grid component
 * This resolves TypeScript compatibility issues with Grid 'item' prop
 * This is a workaround for a known MUI v7 + TypeScript 5.9 compatibility issue
 * 
 * The Grid component in MUI v7 uses conditional types that TypeScript 5.9
 * sometimes fails to resolve. This declaration provides a fallback type.
 */

import '@mui/material';

declare module '@mui/material' {
  namespace Components {
    interface Grid {
      props: {
        item?: boolean;
        container?: boolean;
        xs?: number | boolean | 'auto';
        sm?: number | boolean | 'auto';
        md?: number | boolean | 'auto';
        lg?: number | boolean | 'auto';
        xl?: number | boolean | 'auto';
        [key: string]: any;
      };
    }
  }
}

