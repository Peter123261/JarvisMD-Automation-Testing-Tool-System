/**
 * StatusBadge Component
 * Displays colored status indicators for jobs and evaluations
 */

import { Chip } from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  HourglassEmpty as HourglassIcon,
  Flag as FlagIcon,
} from '@mui/icons-material';

export type StatusType = 'completed' | 'running' | 'failed' | 'pending' | 'flagged' | 'started';

interface StatusBadgeProps {
  status: StatusType;
  size?: 'small' | 'medium';
}

export default function StatusBadge({ status, size = 'small' }: StatusBadgeProps) {
  const getStatusConfig = () => {
    switch (status) {
      case 'completed':
        return {
          label: 'Completed',
          color: 'success' as const,
          icon: <CheckCircleIcon />,
        };
      case 'running':
      case 'started':
        return {
          label: 'Running',
          color: 'info' as const,
          icon: <HourglassIcon />,
        };
      case 'failed':
        return {
          label: 'Failed',
          color: 'error' as const,
          icon: <ErrorIcon />,
        };
      case 'pending':
        return {
          label: 'Pending',
          color: 'default' as const,
          icon: <HourglassIcon />,
        };
      case 'flagged':
        return {
          label: 'Flagged',
          color: 'warning' as const,
          icon: <FlagIcon />,
        };
      default:
        return {
          label: status,
          color: 'default' as const,
          icon: null,
        };
    }
  };

  const config = getStatusConfig();

  return (
    <Chip
      label={config.label}
      color={config.color}
      size={size}
      icon={config.icon || undefined}
      variant="filled"
    />
  );
}
