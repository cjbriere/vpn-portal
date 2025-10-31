# CITS VPN Portal — Collaboration & Delivery Policy

## 1. Core Principles
- Git is the single source of truth. The entire project lives in a private Git repository owned by the user.
- ChatGPT operates in a read-only capacity against the repository’s HEAD state. No assumptions, no invented files, no local drift.
- User maintains all control. Only the user commits, pushes, or merges. ChatGPT never interacts with Git directly.
- Every code output is full and ready-to-use. No partial snippets, no incremental patches. Each deliverable is a complete, deployable file or archive.

## 2. Repository Access
- ChatGPT reads the current live branch (HEAD) via a read-only GitHub or GitLab URL.
- Example: https://github.com/YourUser/vpn-portal
- This gives ChatGPT visibility into all code, templates, configuration files, and schema definitions without uploads.
- ChatGPT uses this view to generate perfectly aligned updates that integrate cleanly with the existing project structure.

## 3. Deliverable Formats
### a. Single-File Updates
- For small or isolated changes, ChatGPT provides the entire file as one code block.
- The user replaces the file in VS Code (or preferred editor), reviews, and commits to Git.

### b. Multi-File or Structural Updates
- When a change affects multiple files, directories, or schemas, ChatGPT supplies a compressed archive (.zip or .tar.gz) containing all relevant files.
- The archive is structured so the user can extract it directly into the project root, validate, and commit.
- Example:
```
cd /opt/vpn-portal
tar -xzf ~/Downloads/vpn-portal_update_2025-11-01.tar.gz
git add .
git commit -m "Apply ChatGPT update 2025-11-01"
```

## 4. No User Uploads
- The user never uploads source archives or databases to ChatGPT.
- All references (including database schema) come from the Git repository.
- If a rebuild or migration is required, ChatGPT produces the scripts or files to be downloaded by the user, not the other way around.

## 5. CHANGELOG.md Protocol
- A CHANGELOG.md file exists at the repository root (/opt/vpn-portal/CHANGELOG.md).
- The user maintains it; ChatGPT will suggest precise entries after each milestone or deliverable.
- Each entry includes date, summary of changes, and the next planned step.
- When starting a new chat or scope, the user pastes only the last 10–15 lines of this changelog so ChatGPT re-synchronizes immediately.
Example:
## 2025-11-01
- Rebuilt clean Flask skeleton
- Added schema importer + admin seeder
- Next: Implement peer management UI

## 6. Thread and Context Efficiency
- Because ChatGPT reads live code from Git, it does not need to retain entire chat history.
- Each new thread references the changelog for continuity and Git for source visibility.
- This keeps memory usage minimal and prevents context loss or guesswork.

## 7. Workflow Summary
| Step | Who | Description |
|------|-----|--------------|
| Code creation / refactor | ChatGPT | Produces full files or archives |
| Review / test / commit | User | Validates and commits changes |
| Repo management | User | Handles branches, merges, pushes |
| CHANGELOG updates | User | Adds ChatGPT-suggested notes |
| New thread bootstrap | User | Paste latest changelog section |
| Context reference | ChatGPT | Reads from Git repo + project memory |

## 8. Results
- Zero guesswork: all references drawn from the actual codebase.
- Zero data loss: changelog + Git history capture every change.
- Zero clutter: clean, efficient threads; only actionable work.
- Zero friction: deliverables ready to extract or drop-in immediately.
