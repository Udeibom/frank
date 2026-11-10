# Job Reliability — Requirements

## Introduction

Long work (beats, mixes, comps, mastering) runs as background jobs that the browser polls. If the worker dies, or the network fails at the moment it records the failure, the job stays `pending` or `processing` forever, and the app waits on work that will never finish. This happened during a real network outage. The Feel Lab design had deferred it (W2). This spec makes every job end in a definite state.

## Requirements

### Requirement 1 — Recording a Failure Survives a Blip

**User Story:** As a user, I want to be told when something didn't work, even if the connection hiccuped at that moment.

#### Acceptance Criteria

1. WHEN a job fails THEN the system SHALL retry recording the failure a few times before giving up.
2. IF every retry fails THEN the system SHALL leave the job for the stale-job check to resolve, and SHALL NOT crash the worker.

### Requirement 2 — Stale Jobs Resolve When Polled

**User Story:** As a user, I want a stuck job to stop looking busy, so that I can try again.

#### Acceptance Criteria

1. WHEN a polled job is `pending` or `processing` and its status has not changed for longer than the stale limit THEN the system SHALL mark it failed with a plain-language message and return that.
2. THE SYSTEM SHALL only change a job that is still active and still stale at the moment of the write, so a job that just completed is never marked failed.
3. THE SYSTEM SHALL never mark a `complete` or `failed` job as stale.
4. THE SYSTEM SHALL set the stale limit well above the longest normal job.

### Requirement 3 — A Restart Clears Orphaned Jobs

**User Story:** As a user on a server that sleeps when idle, I want work that was cut off by a restart to be reported, not left spinning.

#### Acceptance Criteria

1. WHEN the backend starts THEN the system SHALL mark failed every job that was active and last changed before this start, because those jobs ran in a process that no longer exists.
2. IF that sweep cannot reach the database THEN the system SHALL still start.

### Requirement 4 — The Browser Waits Long Enough to Hear the Answer

**User Story:** As a user, I want the app to wait for the server's verdict instead of guessing.

#### Acceptance Criteria

1. THE SYSTEM SHALL keep polling for longer than the stale limit, so a stuck job is reported as failed by the server rather than timed out by the browser.
2. WHILE a job has run for more than a minute THE SYSTEM SHALL poll less often.
