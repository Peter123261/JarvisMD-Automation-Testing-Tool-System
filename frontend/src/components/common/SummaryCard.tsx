/**
 * SummaryCard Component
 * Display summary statistics with icon and color
 */

import React from 'react';
import { Card, CardContent, Typography, Box } from '@mui/material';

interface SummaryCardProps {
  title: string;
  value: string | number;
  subtitle: string;
  icon?: React.ReactNode;
  color?: 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info';
}

export default function SummaryCard({
  title,
  value,
  subtitle,
  icon,
  color = 'primary',
}: SummaryCardProps) {
  return (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" mb={2}>
          {icon && (
            <Box sx={{ mr: 1, color: `${color}.main`, fontSize: 32 }}>
              {icon}
            </Box>
          )}
          <Typography variant="h6" color="text.secondary">
            {title}
          </Typography>
        </Box>
        <Typography variant="h4" color={`${color}.main`} gutterBottom>
          {value}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {subtitle}
        </Typography>
      </CardContent>
    </Card>
  );
}






