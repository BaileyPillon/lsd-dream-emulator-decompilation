/* Standalone compiler reproducer; excluded from the game build. */
struct word_pair {
    int numerator, denominator;
};
typedef struct word_pair pair_alias_t;

static inline int add_pair(struct word_pair value) {
    return value.numerator + value.denominator;
}

int alias_storage_example(int numerator, int denominator) {
    pair_alias_t value;
    value.numerator = numerator;
    value.denominator = denominator;
    return add_pair(value);
}

int tagged_storage_example(int numerator, int denominator) {
    struct word_pair value;
    value.numerator = numerator;
    value.denominator = denominator;
    return add_pair(value);
}

int constructor_example(int numerator, int denominator) {
    return add_pair((struct word_pair) {numerator, denominator});
}
