/**
 * EmptyState Component
 * Displays friendly message when no data is available
 */

import React from 'react';
import { Box, Typography, Button, Paper } from '@mui/material';
import { Inbox as InboxIcon } from '@mui/icons-material';

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  actionLabel?: string;
  onAction?: () => void;
}

export default function EmptyState({
  title,
  description,
  icon,
  actionLabel,
  onAction,
}: EmptyStateProps) {
  return (
    <Paper
      sx={{
        p: 6,
        textAlign: 'center',
        backgroundColor: 'background.default',
      }}
    >
      <Box display="flex" flexDirection="column" alignItems="center" gap={2}>
        {/* Icon */}
        <Box color="text.secondary" sx={{ fontSize: 64 }}>
          {icon || <InboxIcon fontSize="inherit" color="inherit" />}
        </Box>

        {/* Title */}
        <Typography variant="h6" color="text.secondary">
          {title}
        </Typography>

        {/* Description */}
        {description && (
          <Typography variant="body2" color="text.secondary" maxWidth={400}>
            {description}
          </Typography>
        )}

        {/* Action Button */}
        {actionLabel && onAction && (
          <Button variant="contained" onClick={onAction} sx={{ mt: 2 }}>
            {actionLabel}
          </Button>
        )}
      </Box>
    </Paper>
  );
}
