-- avgStrideLength from Garmin is in cm (e.g. 130.5), not meters — widen the column
ALTER TABLE activities
    ALTER COLUMN avg_stride_length TYPE NUMERIC(6,1);
