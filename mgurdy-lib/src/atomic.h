#ifndef _ATOMIC_H
#define _ATOMIC_H

typedef struct {
	volatile int value;
} atomic_t;

#define ATOMIC_INIT(i)  { (i) }

#define atomic_read(v) ((v)->value)

#define atomic_set(v,i) (((v)->value) = (i))

static inline void atomic_add( int i, atomic_t *v )
{
	(void)__sync_add_and_fetch(&v->value, i);
}

static inline void atomic_sub( int i, atomic_t *v )
{
	(void)__sync_sub_and_fetch(&v->value, i);
}

static inline int atomic_sub_and_test( int i, atomic_t *v )
{
	return !(__sync_sub_and_fetch(&v->value, i));
}

static inline void atomic_inc( atomic_t *v )
{
	(void)__sync_fetch_and_add(&v->value, 1);
}

static inline void atomic_dec( atomic_t *v )
{
	(void)__sync_fetch_and_sub(&v->value, 1);
}

static inline int atomic_dec_and_test( atomic_t *v )
{
	return !(__sync_sub_and_fetch(&v->value, 1));
}

static inline int atomic_inc_and_test( atomic_t *v )
{
	return !(__sync_add_and_fetch(&v->value, 1));
}

static inline int atomic_add_negative( int i, atomic_t *v )
{
	return (__sync_add_and_fetch(&v->value, i) < 0);
}

#endif
