/**
 * LoadingSkeleton Component
 * Animated loading placeholders for various content types
 */

import { Box, Skeleton, Card, CardContent, Grid } from '@mui/material';

interface LoadingSkeletonProps {
  variant?: 'card' | 'table' | 'list';
  count?: number;
}

export default function LoadingSkeleton({ variant = 'card', count = 3 }: LoadingSkeletonProps) {
  if (variant === 'card') {
    return (
      <Grid container spacing={3}>
        {Array.from({ length: count }).map((_, index) => (
          <Grid size={{ xs: 12, md: 6, lg: 4 }} key={index}>
            <Card>
              <CardContent>
                <Skeleton variant="text" width="60%" height={32} />
                <Skeleton variant="text" width="40%" height={20} sx={{ mt: 1 }} />
                <Skeleton variant="rectangular" height={100} sx={{ mt: 2, borderRadius: 1 }} />
                <Box display="flex" justifyContent="space-between" mt={2}>
                  <Skeleton variant="text" width="30%" />
                  <Skeleton variant="text" width="20%" />
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    );
  }

  if (variant === 'table') {
    return (
      <Card>
        <CardContent>
          {Array.from({ length: count }).map((_, index) => (
            <Box key={index} display="flex" gap={2} mb={2}>
              <Skeleton variant="rectangular" width={40} height={40} />
              <Box flex={1}>
                <Skeleton variant="text" width="80%" />
                <Skeleton variant="text" width="60%" />
              </Box>
            </Box>
          ))}
        </CardContent>
      </Card>
    );
  }

  // Default list variant
  return (
    <Box>
      {Array.from({ length: count }).map((_, index) => (
        <Box key={index} mb={2}>
          <Skeleton variant="text" width="100%" height={60} />
        </Box>
      ))}
    </Box>
  );
}
