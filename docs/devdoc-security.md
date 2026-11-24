# DevDoc AI Security Controls

DevDoc sends a bounded instruction and JSON context to its configured AI provider. The vendor-neutral `AIProvider` validates requests before provider code runs. The OpenAI adapter uses the existing Responses API architecture with response storage disabled, fixed sanitized exception messages, structured output validation, and configurable request and response byte limits (1,000,000 bytes by default).

## Outbound data checks

The secret scanner detects and redacts common AWS and GitHub keys, password assignments, API and OAuth token assignments, bearer tokens, JWT-like three-part values, database connection URLs, credentials embedded in HTTP(S) URLs, and supported PEM private-key blocks. Incomplete supported private-key blocks are treated as sensitive through the end of the supplied text. Context building omits files containing detected private-key material and applies per-file and aggregate size limits.

The provider gate scans the complete instruction and nested JSON context before a provider request. Values that cannot be serialized as JSON are rejected; their custom string representations are not invoked. Document-type labels are constrained in length and character/word shape before they are included in the generation instruction. API exception details are mapped to fixed messages. Unrecognized or malformed response metadata is omitted, and oversized response text is rejected before JSON parsing.

## Generated output checks

Before the documentation reviewer sees a generated draft, `OutputValidator` treats it as untrusted output and checks it for credentials, high-risk command forms, malformed structure, required sections, and headings associated with a different requested document type. It reuses `SecretScanner`; detected credentials are redacted in the returned draft and reported as validation issues. A draft with any output-validation issue is marked ineligible for the normal human review path. Valid drafts continue to the existing documentation reviewer, and human approval remains mandatory.

Generated commands are never executed. Output validation is separate from the request/context provider gate and from any execution controls. DevDoc does not automatically execute, save, approve, or publish generated documentation.

## Limitations

Secret detection is pattern based. It cannot identify every credential format, encoded or split secrets, arbitrary private-key formats without supported PEM markers, or secrets hidden in binary/unsupported files. JWT-like detection is heuristic and can miss short or unusually encoded tokens or flag token-shaped non-credentials. The HTTP URL matcher covers common user/password authority syntax; it does not decode or inspect every URL encoding scheme. Command checks use a bounded set of patterns and can miss unfamiliar command syntax or flag quoted examples. Heading-based document-type checks can miss semantic drift that does not alter headings. These checks do not prevent prompt injection contained in project files or model output. Human review remains necessary.

The configured byte limits bound serialized request instruction/context and returned response text, not total SDK memory, transport overhead, provider-side processing, or all possible provider metadata. Defaults and sanitization have local unit-test coverage; no external API request or live credential is used by these tests. These controls are not a guarantee that all sensitive information will be detected.
