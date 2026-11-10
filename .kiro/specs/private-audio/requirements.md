# Private Audio — Requirements

## Introduction

Six of Frank's seven storage buckets are public, so anyone holding an audio URL can play a user's takes, beats and mixes without an account. The URLs are unguessable but they are not secret: they sit in browser history, network logs and anything the user shares. This spec makes every bucket private and gives audio out only as short-lived signed links, in responses to the signed-in owner. It builds on the `auth` spec.

## Requirements

### Requirement 1 — Buckets Are Private

**User Story:** As a user, I want my recordings to be reachable only through my own studio, so that nobody can play them from a copied link.

#### Acceptance Criteria

1. THE SYSTEM SHALL mark every storage bucket private.
2. WHEN a stored file is requested by its permanent public-style URL THEN the system SHALL refuse it.

### Requirement 2 — Signed Links in Responses

**User Story:** As a user, I want my audio to keep playing everywhere in the studio exactly as before.

#### Acceptance Criteria

1. WHEN an API response to a signed-in owner contains a storage URL THEN the system SHALL replace it with a signed URL that expires.
2. THE SYSTEM SHALL replace only values that are entirely a storage URL, and SHALL leave every other string, number, and the shape of the JSON unchanged.
3. THE SYSTEM SHALL apply this to every JSON response from one place, so a new endpoint cannot forget it.
4. THE SYSTEM SHALL sign URLs in job results the same way as in direct responses.
5. IF signing fails THEN the system SHALL return the original response rather than an error.

### Requirement 3 — The Backend Can Still Read Its Own Files

**User Story:** As the product, I want background jobs to keep working after the buckets go private.

#### Acceptance Criteria

1. WHEN a job needs a stored file THEN the system SHALL read it through the storage API with the service role, not over a public URL.
2. WHERE a URL is not one of Frank's storage URLs THE SYSTEM SHALL fetch it over HTTP as before.

### Requirement 4 — Nothing Stored Changes

**User Story:** As a developer, I want no data migration for this.

#### Acceptance Criteria

1. THE SYSTEM SHALL keep the stored URL strings in the database unchanged and treat them as permanent references to a file.
2. THE SYSTEM SHALL keep the signing logic inside the backend; the frontend SHALL need no change to play audio.

### Requirement 5 — Efficient and Bounded

**User Story:** As the product, I want polling and list screens to stay fast on a free-tier server.

#### Acceptance Criteria

1. THE SYSTEM SHALL reuse a signed URL for the same file for a limited time instead of signing again on every response.
2. THE SYSTEM SHALL bound the size of that cache.
3. THE SYSTEM SHALL skip all work for responses that contain no storage URL.
