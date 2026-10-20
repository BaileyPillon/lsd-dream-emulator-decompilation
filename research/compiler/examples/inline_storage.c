/* Synthetic compiler diagnostic. This is not game code or a parity fixture. */
typedef struct argument_values {
    int a, b, c, d;
} argument_values_t;

typedef struct frame_sample {
    int x, y, z;
} frame_sample_t;

static inline int combine_values(argument_values_t values) {
    return (values.a - values.b) * (values.c - values.d);
}

int argument_example(int a, int b, int c, int d) {
    return combine_values((argument_values_t){a, b, c, d});
}

void adjust_sample(frame_sample_t *sample) {
    sample->x += sample->y;
    sample->z -= sample->x;
}

static inline int use_local_sample(int x, int y, int z) {
    frame_sample_t sample;
    sample.x = x;
    sample.y = y;
    sample.z = z;
    adjust_sample(&sample);
    return sample.x + sample.y + sample.z;
}

int local_frame_example(int x, int y, int z) {
    return use_local_sample(x, y, z);
}

int enclosing_frame_example(int value) {
    int increment(void) {
        value += 1;
        return value;
    }
    return increment();
}
