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

## 9. Mandatory requirements

1. All implementation, naming, configuration, and procedural decisions must strictly conform to **PROJECT_SCOPE.md** and **COLLABORATION_POLICY.md**.  
2. These two documents are the **only authoritative sources** for all technical and operational details, including directory paths, service names, configuration structures, coding conventions, and deployment procedures.  
3. No prior conversation, historical context, cached assumption, or default model behavior may override, reinterpret, or supplement these documents.  
4. All version control for this project is governed by the Git repository itself (`.git`). The repository state at `HEAD` is the single source of truth for the assistant and the operator.  
5. When a new chat session begins, the assistant must:
   - Load and read the latest committed versions of `PROJECT_SCOPE.md` and `COLLABORATION_POLICY.md` from the active branch.
   - Use `CHANGELOG.md` as the authoritative timeline of revisions, decisions, and implementation history.
   - Acknowledge the current commit hash or version tag (e.g., “Loaded PROJECT_SCOPE.md@<commit_hash>”) before performing any work.
   - Ignore all prior conversational history not reflected in the Git repository.
6. Any instruction, command, or code output that conflicts with these governing documents or the repository state must be flagged immediately for clarification before proceeding.
7. The assistant must include an **optional Git update reminder** only after a complete, verifiable step or milestone—not after every command.  
   Example:
   ```bash
   # (optional) record this step once verified
   git add .
   git commit -m "Phase 1 - Step 2: environment + venv setup complete"
   git push

### 9.x Privilege model

- Provisioning and deployment steps assume the operator is **root** on the target host.
- The project root is **/opt/vpn-portal**, owned recursively by `vpnportal:vpnportal`.
- Files that must be writable at runtime by the app (e.g., generated QR codes, logs if file-based) are owned by `vpnportal` and mode 0640/0750 as appropriate.
- The `vpnportal` user has **no general sudo**; only the least-privilege commands allowed in `/etc/sudoers.d/99-vpnportal` (WireGuard runtime, limited service reloads, read-only network introspection).
- When commands are shown with `sudo -u vpnportal …`, they are *optional* when operating as root; the authoritative ownership remains `vpnportal:vpnportal`.
