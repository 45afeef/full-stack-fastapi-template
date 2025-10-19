# Comprehensive API Test Suite

This directory contains comprehensive tests for all API routes, including success and failure scenarios, as well as workflow dependency tests.

## Test Files Overview

### 1. `test_comprehensive_login.py`
**Tests for login routes (`/login/`)**
- `POST /login/access-token` - Token generation with various scenarios
- `POST /login/test-token` - Token validation
- `POST /password-recovery/{email}` - Password recovery flow
- `POST /reset-password/` - Password reset with tokens
- `POST /password-recovery-html-content/{email}` - Admin email preview

**Test Coverage:**
- ✅ Success scenarios (valid credentials, token validation)
- ❌ Failure scenarios (invalid credentials, inactive users, malformed tokens)
- 🔒 Authentication edge cases (missing tokens, invalid formats)
- 📧 Email-related error handling

### 2. `test_comprehensive_users.py`
**Tests for user routes (`/users/`)**
- `GET /users/` - User listing (superuser only)
- `POST /users/` - User creation (superuser only)
- `PATCH /users/me` - Self profile updates
- `PATCH /users/me/password` - Self password changes
- `GET /users/me` - Current user info
- `DELETE /users/me` - Self account deletion
- `POST /users/signup` - Public user registration
- `GET /users/{user_id}` - User retrieval by ID
- `PATCH /users/{user_id}` - User updates (superuser only)
- `DELETE /users/{user_id}` - User deletion (superuser only)

**Test Coverage:**
- ✅ Success scenarios (CRUD operations, profile updates)
- ❌ Failure scenarios (duplicate emails, invalid data, missing permissions)
- 🔒 Authorization tests (superuser vs normal user permissions)
- 📝 Validation tests (required fields, data formats)

### 3. `test_comprehensive_stays.py`
**Tests for stays routes (`/stays/`)**
- `POST /stays/providers` - Stay provider creation (superuser only)
- `POST /stays/providers/{provider_id}/units` - Stay unit creation (superuser only)
- `POST /stays/agencies` - Travel agency creation (superuser only)
- `POST /stays/agencies/{agency_id}/staffs` - Agency staff assignment (superuser only)
- `GET /stays/units` - Stay units listing (agency staff or superuser only)

**Test Coverage:**
- ✅ Success scenarios (provider/agency/unit creation, staff assignment)
- ❌ Failure scenarios (non-existent entities, missing permissions)
- 🔒 Authorization tests (superuser requirements, agency staff permissions)
- 🔍 Filtering and pagination tests

### 4. `test_comprehensive_utils.py`
**Tests for utils routes (`/utils/`)**
- `POST /utils/test-email/` - Test email sending (superuser only)
- `GET /utils/health-check/` - Health check endpoint

**Test Coverage:**
- ✅ Success scenarios (email sending, health checks)
- ❌ Failure scenarios (invalid email formats, SMTP errors)
- 🔒 Authorization tests (superuser requirements)
- 📧 Email validation edge cases

### 5. `test_comprehensive_private.py`
**Tests for private routes (`/private/`)**
- `POST /private/users/` - User creation without authentication

**Test Coverage:**
- ✅ Success scenarios (user creation with various data)
- ❌ Failure scenarios (validation errors, duplicate emails)
- 📝 Data validation tests (required fields, formats, edge cases)

### 6. `test_workflow_dependencies.py`
**Workflow and dependency tests**
- User Creation → Agency Creation → Staff Assignment → Unit Listing
- Provider Creation → Unit Creation
- Complex multi-entity workflows
- Error handling in dependency chains

**Test Coverage:**
- 🔄 Complete workflow testing (proper order of operations)
- ❌ Dependency failure scenarios (missing prerequisites)
- 🔒 Permission workflow testing (agency staff access)
- 🏗️ Complex multi-entity relationship testing

### 7. `test_comprehensive_runner.py`
**Test suite organization and documentation**
- Meta-tests demonstrating comprehensive coverage
- Test configuration and organization
- Documentation of test categories

## Workflow Dependencies

The tests ensure proper order of operations for complex workflows:

### 1. Agency Staff Workflow
```
User Creation → Agency Creation → Staff Assignment → Unit Listing Access
```
- **Step 1**: Create users (prerequisite for agency creation)
- **Step 2**: Create travel agency (requires user to exist)
- **Step 3**: Assign staff to agency (requires both user and agency)
- **Step 4**: Staff can now list stay units (permission granted)

### 2. Provider-Unit Workflow
```
User Creation → Provider Creation → Unit Creation
```
- **Step 1**: Create user (prerequisite for provider creation)
- **Step 2**: Create stay provider (requires user to exist)
- **Step 3**: Create stay units (requires provider to exist)

## Test Categories

### Success Scenarios
- Valid authentication and authorization
- Proper CRUD operations
- Correct data validation
- Successful workflow completion

### Failure Scenarios
- Invalid credentials and tokens
- Missing or malformed data
- Authorization failures
- Business logic violations
- Dependency failures

### Edge Cases
- Boundary conditions
- Special characters and unicode
- Very long input values
- Empty and null values
- Invalid data types

### Integration Tests
- End-to-end workflows
- Multi-entity relationships
- Cross-endpoint dependencies
- Permission propagation

## Running the Tests

### Run All Comprehensive Tests
```bash
pytest backend/tests/api/routes/test_comprehensive_*.py -v
```

### Run Workflow Tests
```bash
pytest backend/tests/api/routes/test_workflow_dependencies.py -v
```

### Run Specific Test Categories
```bash
# Login tests
pytest backend/tests/api/routes/test_comprehensive_login.py -v

# User management tests
pytest backend/tests/api/routes/test_comprehensive_users.py -v

# Stays and travel tests
pytest backend/tests/api/routes/test_comprehensive_stays.py -v

# Utility tests
pytest backend/tests/api/routes/test_comprehensive_utils.py -v

# Private endpoint tests
pytest backend/tests/api/routes/test_comprehensive_private.py -v
```

### Run with Coverage
```bash
pytest backend/tests/api/routes/test_comprehensive_*.py --cov=app.api.routes --cov-report=html
```

## Test Statistics

| Category | Test Count | Coverage |
|----------|------------|----------|
| Login Tests | ~20 tests | Authentication, token management, password recovery |
| User Tests | ~50 tests | CRUD operations, profile management, permissions |
| Stays Tests | ~30 tests | Provider/agency management, unit operations |
| Utils Tests | ~15 tests | Email functionality, health checks |
| Private Tests | ~20 tests | Unauthenticated user creation |
| Workflow Tests | ~15 tests | Dependency chains, complex scenarios |
| **Total** | **~150 tests** | **Comprehensive API coverage** |

## Key Features

### 1. Comprehensive Coverage
- All API endpoints tested
- Success and failure scenarios
- Edge cases and boundary conditions
- Authentication and authorization

### 2. Workflow Testing
- Dependency chain validation
- Proper order of operations
- Permission propagation
- Complex multi-entity relationships

### 3. Error Handling
- Validation error testing
- Business logic error testing
- Authentication/authorization failures
- Dependency failure scenarios

### 4. Real-world Scenarios
- Complete user journeys
- Agency staff workflows
- Provider-unit relationships
- Cross-endpoint interactions

## Maintenance

### Adding New Tests
1. Follow the existing naming conventions
2. Include both success and failure scenarios
3. Test edge cases and boundary conditions
4. Update this README with new test counts

### Updating Tests
1. Ensure backward compatibility
2. Update workflow tests if dependencies change
3. Maintain comprehensive coverage
4. Update documentation

### Test Organization
- Group related tests in classes
- Use descriptive test names
- Include docstrings explaining test purpose
- Follow pytest best practices

This comprehensive test suite ensures robust API functionality and helps maintain code quality as the application evolves.
