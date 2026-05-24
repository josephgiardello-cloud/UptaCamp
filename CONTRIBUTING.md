# Contributing to UptaCamp

Thank you for your interest in contributing to **UptaCamp**! 🎉 This document provides guidelines and instructions for contributing to the project.

## How to Contribute

### Reporting Bugs

Found a bug? Please open an [Issue](https://github.com/josephgiardello-cloud/UptaCamp/issues) with the following information:

1. **Title**: Brief description of the bug
2. **Description**: Clear explanation of what went wrong
3. **Steps to Reproduce**:
   - How to trigger the bug
   - Expected vs. actual behavior
4. **Environment**:
   - Python version
   - Pygame version
   - Operating system
5. **Screenshots/Logs**: Attach if relevant

**Example**:
```
Title: AI plays invalid cards at total 25
Description: When pegging total is 25, Dealer AI selects cards that would make 32+
Steps to Reproduce:
1. Start game on Hard difficulty
2. Play to a pegging total of 25
3. Watch Dealer's move
Expected: Dealer should play a card ≤ 6
Actual: Dealer plays a 7 or higher
```

### Suggesting Features

Have an idea? Open an [Issue](https://github.com/josephgiardello-cloud/UptaCamp/issues) labeled `enhancement`:

1. **Describe the feature**: What problem does it solve?
2. **Proposed solution**: How should it work?
3. **Alternatives**: Other approaches you considered
4. **Additional context**: Screenshots, mockups, or examples

**Example**:
```
Title: Add multiplayer support
Description: Allow two human players to play locally
Proposed Solution: 
- Add "Player vs Player" mode in intro
- Hide opponent's cards with card-back graphics
- Alternate turns with clear indicators
```

### Submitting Code

#### Setup

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/UptaCamp.git
   cd UptaCamp
   ```

3. **Create a virtual environment**:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate          # Windows
   source .venv/bin/activate      # macOS/Linux
   ```

4. **Install development dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

#### Development Workflow

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```
   Use descriptive names: `feature/hard-ai-improvement`, `fix/pegging-bug`, `docs/add-screenshots`

2. **Make your changes**:
   - Keep commits small and focused
   - Write clear commit messages
   - Update docstrings and comments

3. **Run tests**:
   ```bash
   pytest tests/
   ```

4. **Check code quality**:
   ```bash
   ruff check .
   black --check .
   ```

5. **Fix any issues**:
   ```bash
   ruff check . --fix
   black .
   ```

6. **Commit your changes**:
   ```bash
   git add .
   git commit -m "feat: Add new AI decision logic for pegging"
   ```
   Use conventional commits:
   - `feat:` new feature
   - `fix:` bug fix
   - `docs:` documentation
   - `style:` formatting
   - `refactor:` code restructuring
   - `test:` adding/updating tests

7. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

8. **Open a Pull Request**:
   - Go to https://github.com/josephgiardello-cloud/UptaCamp/pulls
   - Click "New Pull Request"
   - Select your fork and branch
   - Fill in the PR template
   - Link related issues with `Closes #123`

#### Pull Request Guidelines

Your PR should:
- ✅ Solve a single issue or implement a single feature
- ✅ Include tests for new functionality
- ✅ Update documentation if needed
- ✅ Pass all CI checks (tests, linting)
- ✅ Have clear commit history
- ✅ Include a descriptive title and description

**Example PR Description**:
```
## Description
Improves Hard AI pegging strategy by considering opponent hand size.

## Related Issue
Closes #42

## Changes
- Modified `_estimate_opponent_reply_risk()` to scale simulations by opponent hand
- Added opponent hand size as context to risk calculation
- Updated tests for new logic

## Testing
- [x] New tests pass
- [x] Existing tests pass
- [x] Manual testing on Hard difficulty

## Checklist
- [x] Code follows style guidelines
- [x] Documentation updated
- [x] No new warnings generated
```

## Development Standards

### Code Style

- **Python**: Follow [PEP 8](https://pep8.org/)
- **Line Length**: 100 characters max
- **Formatter**: [Black](https://black.readthedocs.io/)
- **Linter**: [Ruff](https://github.com/astral-sh/ruff)

### Commits

Format: `<type>(<scope>): <subject>`

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style (formatting)
- `refactor`: Code refactoring
- `test`: Tests
- `chore`: Build/dependencies

**Examples**:
```
feat(ai): Add opponent risk simulation for hard mode
fix(pegging): Prevent invalid card plays at total 31
docs(readme): Add difficulty level explanations
test(scoring): Add hand scoring edge cases
```

### Testing

- Write tests for new features
- Ensure tests pass: `pytest`
- Aim for >80% coverage on new code
- Test edge cases and error conditions

### Documentation

- Add docstrings to functions and classes
- Update README.md if adding features
- Include inline comments for complex logic
- Keep comments up-to-date with code changes

## Git Workflow

```
main branch (stable releases)
  ↑
  |-- (Pull Requests reviewed & merged)
  |
Your Fork
  ↓
feature/your-feature (local work)
  ↓
Push to GitHub
  ↓
Open Pull Request
  ↓
Review & Feedback
  ↓
Merge to main
```

## Getting Help

- **Questions?** Open a [Discussion](https://github.com/josephgiardello-cloud/UptaCamp/discussions)
- **Issues?** Check [existing issues](https://github.com/josephgiardello-cloud/UptaCamp/issues) first
- **Want to chat?** Comment on related PRs/issues

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

**Thank you for making UptaCamp better! 🙏**
