<h1>Way of Working (WoW)</h1>

## Partnering

- Work technically together with actively participating EU Member States
- Work technically together with actively participating platforms
- Take shared, commonly supported design decisions
- Implement changes quick, to stay agile
- Use GitHub tags for initial versioning
- Use API versioning later (once competent authorities and platforms are connected)

## Issue Management

- **Anyone** can enter new issues
- **Team SDEP (NL)** assigns (exactly one) **label** to the issue and puts it into the SDEP **project**
- **Anyone** can enter comments in (closed) issues

## Issue Labels

Each issue is assigned exactly one label:

| **Label**       | **Description**                                                           |
| --------------- | ------------------------------------------------------------------------- |
| *(Empty)*       | Newly created issue; intake/triage pending                                |
| **Analyze**     | Requires analysis by Team SDEP (NL)                                       |
| **Propose**     | Requires discussion and proposal by the Technical Working Group (**TWG**) |
| **Agreed**      | Reviewed and agreed upon by the Technical Working Group (**TWG**) [1]     |
| **EC**          | Pending decision by the European Commission                               |
| **Enhancement** | Standard enhancement to the reference implementation or documentation     |
| **Bug**         | Defect in the reference implementation or documentation                   |

[1] Unless commented otherwise: This label is added 72h after discussion/agreement, after which it will be implemented.

## Work in Progress

- **Team SDEP (NL)** maintains work in progress on **Kanban boards** in **milestones**
- **Collaborators** can see the project's Kanban boards
- https://github.com/orgs/SEMICeu/projects/3/views/1?groupedBy%5BcolumnId%5D=Milestone

## Work Completed

- Change log - https://github.com/SEMICeu/sdep/blob/main/CHANGELOG.md
- Closed issues - https://github.com/SEMICeu/sdep/issues?q=is%3Aissue%20state%3Aclosed



## GitHub — Manual for New Users (SDEP)
 
This manual is for people from the business side who want to follow issues and discussions in the SDEP GitHub repositories — no technical background required.
 
**Relevant links:**
- Issues: https://github.com/SEMICeu/sdep/issues
- Project board: https://github.com/orgs/SEMICeu/projects/3
 
---
 
### Step 1 — Create a GitHub account
 
1. Go to https://github.com
2. Click **Sign up**
3. Enter your email address, choose a username and password
4. Verify your email address via the confirmation mail
5. You now have a free GitHub account
 
> A free account is sufficient — no paid plan needed.
 
---
 
### Step 2 — Become a collaborator
 
To receive notifications and participate in discussions, you need to be added to the SDEP repository.
 
**Ask the repository administrator to invite you** (provide them with your GitHub username or the email address you registered with).
 
You will receive an invitation by email — click **Accept invitation** to confirm.
 
> Without an invitation you can still view public issues, but you will not receive notifications automatically.
 
---
 
### Step 3 — Set up notifications
 
#### Watch the repository
 
1. Go to https://github.com/SEMICeu/sdep
2. Click the **Watch** button (top right, next to Star)
3. Choose your preferred level:
 
| Option | What you receive |
|---|---|
| **Participating and @mentions** | Only issues/comments where you are directly involved or mentioned |
| **All activity** | Every new issue, comment, and status change |
| **Custom** | Choose specific events (e.g. issues only, no pull requests) |
 
> **Recommended for business users:** choose **All activity** or **Custom → Issues** so you are notified of every new issue and discussion.
 
#### Watch the project board
 
1. Go to https://github.com/orgs/SEMICeu/projects/3
2. GitHub does not send direct notifications for project board changes, but issues linked to the board will still trigger notifications if you watch the repository.
 
#### Notification delivery
 
Go to **GitHub → Settings → Notifications** to choose how you receive notifications:
 
- **Email** — notifications arrive in your inbox (recommended)
- **Web** — notifications appear inside GitHub only (bell icon)
- Both can be enabled simultaneously
 
---
 
### Step 4 — Filter notifications in your email client
 
GitHub notification emails all come from `notifications@github.com` and contain consistent subject lines and headers. You can use these to automatically move them to a dedicated folder.
 