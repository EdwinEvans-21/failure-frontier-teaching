class Solution:

    def minOperations(self, s1: str, s2: str) -> int:
        infinity = len(s1) + 1
        dp = [0, infinity]

        for index, (source_bit, target_bit) in enumerate(zip(s1, s2)):
            must_decrease = source_bit == "1" and target_bit == "0"
            next_dp = [infinity, infinity]
            right_choices = (0,) if index == len(s1) - 1 else (0, 1)

            for selected_left in (0, 1):
                for selected_right in right_choices:
                    if must_decrease and not (
                        selected_left or selected_right
                    ):
                        continue
                    candidate = dp[selected_left] + selected_right
                    next_dp[selected_right] = min(
                        next_dp[selected_right], candidate
                    )
            dp = next_dp

        if dp[0] == infinity:
            return -1
        return s2.count("1") - s1.count("1") + 3 * dp[0]
