class Solution:
    def minimumOneBitOperations(self, n: int) -> int:
        if n == 0:
            return 0
        bit = n.bit_length() - 1
        return (1 << (bit + 1)) - 1 - self.minimumOneBitOperations(n ^ (1 << bit))
