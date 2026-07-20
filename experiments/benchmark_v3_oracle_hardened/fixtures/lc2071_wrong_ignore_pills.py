class Solution:
    def maxTaskAssign(self, tasks, workers, pills, strength):
        tasks.sort()
        workers.sort()
        done = i = 0
        for worker in workers:
            if i < len(tasks) and tasks[i] <= worker:
                done += 1
                i += 1
        return done
