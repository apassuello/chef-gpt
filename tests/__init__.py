"""
Test suite for the Anova Sous Vide Assistant Server.

Test organization:
- test_validators.py: Unit tests for input validation and food safety
- test_routes.py: Integration tests for HTTP endpoints
- test_anova_client.py: Tests for Anova API client with mocks
- conftest.py: Shared pytest fixtures

Testing philosophy:
- Unit tests for validators (>80% coverage goal)
- Integration tests for routes (full request/response cycle)
- Mock external dependencies (don't call real Anova API)
- Test ALL food safety edge cases

Reference: CLAUDE.md Section "Testing Strategy"
"""
