# SSO Stakeholder Communication Templates

## Initial Check-in (When Admin Access is Needed)

### Template: Requesting Admin Access
```
Hey [Stakeholder Name] - I have your ticket for the [App Name] SSO. Sorry for the delay in actioning this one. I've got it slated for this sprint!

Would you be able to provide super admin access to it-admin@example.com when you have a chance? That'll allow me to integrate the app with Okta.
```

**Usage**: Send when starting SSO work and need admin credentials

---

## Follow-up (If No Response)

### Template: Gentle Bump
```
Hey [Stakeholder Name], just wanted to bump on this. Is this still needed?

I still have the ticket.
```

**Usage**: Send after 3-5 days of no response on admin access request

---

## Confirmation (Once Admin Access Received)

### Template: Work Confirmation & Timeline
```
Thank you! I'm in. I should be able to finish this up by [Day/Date] as long as no blockers are hit.

During the process, I'll set up SSO, test, then setup the Freshservice catalog item/provisioning and add any users you have in the RBAC template. After that, I'll confirm with you that everything is working before sending out an email to the userbase that they should now use Okta to access.

If I have any questions, I'll send you another DM!
```

**Usage**: Send immediately after receiving admin access confirmation
**Customize**: Replace [Day/Date] with realistic completion date (typically 3-5 business days)

---

## Mid-Process Check-in

### Template: Testing Phase Update
```
Hey [Stakeholder Name] - Quick update on [App Name] SSO:

✅ Okta SSO configured
✅ Test account validated
🔄 Currently: Setting up Freshservice catalog and provisioning workflow

Next steps:
- Add your users from RBAC template
- Final validation with you
- Go-live communications

Still on track for [Day/Date] completion. Will ping you for validation testing soon!
```

**Usage**: Optional - send midway through process if stakeholder is anxious or project is high-visibility

---

## Pre-Go-Live Validation

### Template: Ready for Stakeholder Testing
```
Hey [Stakeholder Name] - [App Name] SSO is ready for validation!

What's been set up:
✅ Okta SSO integration
✅ Freshservice catalog item for access requests
✅ Automated provisioning workflow
✅ Users from your RBAC template added

Can you (or someone on your team) test the following?
1. Log into Okta
2. Click the [App Name] tile
3. Verify you land in the app with correct permissions
4. Try [any app-specific functionality to test]

Let me know if everything looks good, and I'll send the go-live email to your team!
```

**Usage**: Send when SSO is fully configured and ready for stakeholder validation

---

## Go-Live Announcement (To End Users)

### Template: Go-Live Email
```
Subject: [App Name] - Now Live with Okta SSO

Hello Team,

I hope this message finds you well. This email serves as official notice that [App Name] is now live with Okta SSO. Going forward, please log in via your Okta Dashboard by clicking on the [App Name] tile.

How to Access:
1. Log into your Okta Dashboard: https://yourorg.okta.com
2. Click the [App Name] tile
3. You'll be automatically logged in with your company credentials

[Optional: Add screenshots of Okta tile]

[If special instructions needed]:
• [Special instruction 1]
• [Special instruction 2]

If you have any questions or encounter any issues, please submit a ticket to IT: https://yourorg.freshservice.com

Best regards,
[Your Name]
Global IT - Systems Team
```

**Customization**:
- Replace [App Name] with actual application name
- Add screenshots showing the Okta tile (if helpful)
- Include any special login instructions (e.g., organization name, subdomain)
- Adjust tone/formality based on company culture
- CC: Stakeholder, IT Manager (optional)

**Usage**: Send after stakeholder validates everything is working

---

## Post-Go-Live Follow-up

### Template: 1-Week Check-in
```
Hey [Stakeholder Name] - Quick check-in on [App Name] SSO (went live [Date]).

Have you heard any feedback from your team? Any issues or questions coming up?

If everything is smooth, great! If there are any hiccups, let me know and I'll jump on it.
```

**Usage**: Send 1 week after go-live to catch any issues early

---

## Internal IT Notification (Slack)

### Template: Global IT Announcement
```
Hey all, heads up!
🎉 New SSO just dropped! - [App Name] 🎉

• Okta SSO App: [Okta App URL]
• Service Catalog Item: [Service Catalog URL]
• Automated Workflow: [Workflow URL]
• Trelica: [Trelica URL] ✅ OR • Trelica: [PENDING - To be configured]

This app is owned by [Stakeholder Name].

SSO with [OIDC/SCIM] provisioning for all roles!
*Note:* [Add any important notes about provisioning/deprovisioning capabilities]

*Roles & Approval Process:*
- *[Role1]* role: Auto-approved via service catalogue
- *[Role2]* role: Requires approval from [Approver1], [Approver2], or [Approver3]

*Important Note for Users:*
[Add any special login instructions]

*Quick Links:*
- Okta Groups:
  - [app]_[role1]: [Group URL]
  - [app]_[role2]: [Group URL]
- Service Catalog: [Service Catalog URL]
- Workflow: [Workflow URL]
```

**Usage**: Post in #it-global or internal IT Slack channel after go-live
**Fun variations**: "New SSO out in the wild!", "Fresh SSO incoming!", "SSO launch incoming!"

---

## Process Reminder Checklist

When communicating with stakeholders, remember to handle these steps internally:

**Before Go-Live:**
- [ ] Admin access to it-admin@example.com secured
- [ ] RBAC template received and reviewed
- [ ] Okta SSO configured
- [ ] Okta groups created (APP-[AppName]-[RoleName])
- [ ] Freshservice catalog item created
- [ ] Freshservice workflow automation configured
- [ ] **Trelica updated** (license management)
- [ ] Test account validation completed
- [ ] Seed users added and validated
- [ ] Stakeholder validation completed

**At Go-Live:**
- [ ] Go-live email sent to end users
- [ ] **Global IT notified** (Slack post)
- [ ] Knowledge base article created
- [ ] Help desk briefed (if needed)

**Post Go-Live:**
- [ ] Monitor for issues (first 2 weeks)
- [ ] 1-week stakeholder check-in
- [ ] Update documentation with any lessons learned

---

## Quick Reference: Timeline Estimates

| Task | Estimated Time | Notes |
|------|----------------|-------|
| Admin access secured | 1-3 days | Depends on stakeholder responsiveness |
| Okta SSO configuration | 2-4 hours | Including group setup |
| Freshservice catalog + workflow | 3-5 hours | Complex workflows take longer |
| Trelica update | 30 minutes | If app already in Trelica |
| Testing & validation | 1-2 hours | Including stakeholder testing |
| Communications | 1 hour | Drafting + sending emails |
| **Total end-to-end** | **3-5 business days** | From admin access to go-live |

**Rule of thumb**: Promise Friday if starting Monday-Tuesday, promise next week if starting Wednesday-Thursday
