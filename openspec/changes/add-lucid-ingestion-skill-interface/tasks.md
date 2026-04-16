## 1. OpenSpec Proposal and Design

- [ ] 1.1 Finalize the proposal for the Lucid ingestion skill interface
- [ ] 1.2 Finalize the technical design for the search/skip/write decision flow and Graphiti write envelope

## 2. Skill Interface Specifications

- [ ] 2.1 Define the `ingestion-skill-interface` capability for agent-side memory usage policy
- [ ] 2.2 Define the `graphiti-write-envelope` capability for shaping Graphiti writes through the current MCP contract

## 3. Skill and Documentation Updates

- [ ] 3.1 Update `skills/lucid-memory` with search/skip/write guidance
- [ ] 3.2 Add source-selection guidance for `json`, `text`, and `message`
- [ ] 3.3 Document the current limitation that `custom_extraction_instructions` is not available through the MCP write path

## 4. Validation

- [ ] 4.1 Validate the OpenSpec change with the local `openspec` CLI
- [ ] 4.2 Smoke-test the guidance against at least one curated `json` write and one `text` write

## 5. Follow-Through

- [ ] 5.1 After implementation, update the Lucid design documentation to reflect the final implemented behavior and any deviations from this proposal
