.macro glabel label
    .global \label
	.type \label, @function
    \label:
.endm

# Metadata emitted by current spimdisasm; these do not emit instructions.
.macro nonmatching label, size
.endm

.macro endlabel label
    .size \label, . - \label
.endm

.macro enddlabel label
    .size \label, . - \label
.endm

.macro alabel label
    .global \label
\label:
.endm

.macro dlabel label
    .global \label
    \label:
.endm

.macro jlabel label
    .global \label
    \label:
.endm

.macro .def #
.endm

.macro move a, b
    addu \a, \b, $zero
.endm

.include "gte.inc"
