//! xorshift32 — must match the on-cart C implementation bit-for-bit.

#[derive(Copy, Clone, Debug)]
pub struct Xorshift32 { state: u32 }

impl Xorshift32 {
    pub const fn new(seed: u32) -> Self {
        // Seed 0 is degenerate for xorshift; snap to a fixed nonzero.
        let s = if seed == 0 { 0xDEAD_BEEF } else { seed };
        Self { state: s }
    }

    pub fn next_u32(&mut self) -> u32 {
        let mut x = self.state;
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
        self.state = x;
        x
    }

    pub fn next_u8(&mut self) -> u8 { (self.next_u32() & 0xFF) as u8 }

    /// Mirror of the cart's `rng_range(u8 n)`: one full draw, the LOW BYTE
    /// reduced mod n. (Not `next_u32() % n` — both call order AND the
    /// reduction must match the C or every downstream value diverges.)
    pub fn range_u8(&mut self, n: u8) -> u8 {
        if n == 0 { 0 } else { self.next_u8() % n }
    }

    /// Mirror of the cart's `rng_range16(u16 n)`.
    pub fn range_u16(&mut self, n: u16) -> u16 {
        if n == 0 { 0 } else { ((self.next_u32() & 0xFFFF) as u16) % n }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn deterministic() {
        let mut a = Xorshift32::new(42);
        let mut b = Xorshift32::new(42);
        for _ in 0..1000 {
            assert_eq!(a.next_u32(), b.next_u32());
        }
    }

    #[test]
    fn zero_seed_handled() {
        let mut r = Xorshift32::new(0);
        let v = r.next_u32();
        assert!(v != 0);
    }
}
