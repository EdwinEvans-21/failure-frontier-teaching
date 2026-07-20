# Offline fixtures

The iterative tests construct a complete temporary frozen-root episode from public repository artifacts and use `ScriptedOfflineModel`, `DeterministicFakeJudge`, and `DeterministicFlatPipeline`. No fixture starts Docker, opens a socket, reads an API key, or invokes a real evaluator. Temporary root manifests are raw-byte SHA-256 locked before execution.

The fixture scenarios cover AC stopping, ordinary WA inheritance, standardized RE/CE/TLE/MLE payloads, missing fenced code, Flat FF protocol failure, resume, direct-parent isolation, and root/parent hash drift.
