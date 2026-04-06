# SSO Configuration Runbook

## Overview
This runbook provides a step-by-step process for configuring Single Sign-On (SSO) and SCIM provisioning for new applications at your company. Follow each phase sequentially to ensure proper setup and testing.

---

## Phase 1: Intake & Documentation

### Step 1.1: Send RBAC Google Sheet
**Objective**: Gather role and access requirements from the customer team

**Actions**:
- [ ] Send RBAC Google Sheet template to stakeholder
- [ ] Include instructions for completing the sheet
- [ ] Set deadline for completion (typically 3-5 business days)

**Required Information**:
- User roles and permissions needed
- Team structure
- Access level requirements
- Point of contact for questions

**Stakeholders**: Customer team lead, IT Admin

---

### Step 1.2: Convert to Jira Ticket
**Objective**: Track SSO configuration work in project management system

**Actions**:
- [ ] Wait for confirmation that RBAC sheet is complete
- [ ] Review RBAC sheet for completeness and clarity
- [ ] Convert Freshservice ticket to Jira ticket
- [ ] Link RBAC sheet in Jira ticket description
- [ ] Assign to SSO configuration team
- [ ] Set appropriate priority and labels

**Deliverables**:
- Jira ticket with complete context
- RBAC sheet validated and attached

---

## Phase 2: Administrative Access Setup

### Step 2.1: Request Super Admin Access
**Objective**: Ensure it-admin@example.com has necessary permissions for configuration

**Actions**:
- [ ] Contact application vendor or customer admin
- [ ] Request super admin privileges for it-admin@example.com
- [ ] Verify access has been granted
- [ ] Document access credentials in secure credential vault
- [ ] Test login to confirm permissions

**Security Notes**:
- Use credential management system for storing credentials
- Enable MFA if available
- Document access level granted

**Blockers**: If super admin cannot be granted, escalate to IT Security team

---

## Phase 3: Identity Provider Configuration

### Step 3.1: Create Freshservice Custom Object for Roles
**Objective**: Structure role data for automated provisioning

**Actions**:
- [ ] Navigate to Freshservice Admin → Custom Objects
- [ ] Create new custom object: `[AppName]_Roles`
- [ ] Define fields:
  - Role Name (Text, Required)
  - Role Description (Text)
  - Permission Level (Dropdown: Admin, User, Read-Only)
  - Okta Group Mapping (Text)
  - Application Entitlements (Multi-line Text)
- [ ] Set up relationships to User object
- [ ] Configure visibility and access controls
- [ ] Import role data from RBAC sheet

**Custom Object Structure**:
```
Object Name: [AppName]_Roles
Fields:
  - role_name: string (unique)
  - role_description: string
  - permission_level: enum
  - okta_group_name: string
  - entitlements: array
  - created_date: datetime
  - updated_date: datetime
```

---

### Step 3.2: Create Okta App Groups
**Objective**: Set up identity groups in Okta for role-based access

**Actions**:
- [ ] Log into Okta Admin Console
- [ ] Navigate to Directory → Groups
- [ ] Create groups for each role from RBAC sheet
- [ ] Follow naming convention: `APP-[AppName]-[RoleName]`
- [ ] Add group descriptions from RBAC data
- [ ] Configure group rules if using dynamic membership
- [ ] Document group IDs in configuration tracking sheet

**Naming Convention**:
- Format: `APP-[AppName]-[RoleName]`
- Example: `APP-Salesforce-Sales-Manager`
- Use kebab-case for multi-word names

**Group Attributes**:
- Description: Role purpose and permissions
- Group Type: Okta Group (not AD-synced unless specified)
- Group Rules: Configure if using attribute-based assignment

---

## Phase 4: Self-Service Provisioning Setup

### Step 4.1: Create Freshservice Service Catalogue Item
**Objective**: Enable users to request access through self-service portal

**Actions**:
- [ ] Navigate to Freshservice Admin → Service Catalog
- [ ] Create new service item: `[AppName] - Access Request`
- [ ] Configure item details:
  - Name: `[AppName] Access Request`
  - Short Description: Brief app description
  - Category: Application Access
  - Item Icon: Upload app logo if available
- [ ] Create custom form fields:
  - Role Requested (Dropdown from custom object)
  - Business Justification (Text area, Required)
  - Manager Approval Required (Checkbox)
  - Access Duration (Dropdown: Permanent, 30 days, 60 days, 90 days)
- [ ] Set up approval workflow
- [ ] Configure fulfillment instructions
- [ ] Test form submission

**Form Fields**:
```
1. Requested Role: [Dropdown from AppName_Roles custom object]
2. Business Justification: [Text Area, Required, Min 50 chars]
3. Cost Center: [Dropdown from Finance data]
4. Manager Approval: [Auto-filled from user profile]
5. Access Duration: [Dropdown: Permanent/Temporary]
6. Additional Requirements: [Text Area, Optional]
```

---

### Step 4.2: Create Freshservice Workflow Automation
**Objective**: Automate provisioning process from request to Okta group assignment

**Actions**:
- [ ] Navigate to Freshservice Admin → Workflows → Automator
- [ ] Create new workflow: `[AppName] - Provisioning Workflow`
- [ ] Configure workflow trigger: Service request submitted for [AppName] catalogue item
- [ ] Add workflow steps:
  1. Send notification to manager for approval
  2. On approval: Assign to IT provisioning team
  3. Create Okta API call to add user to group
  4. Update custom object with user assignment
  5. Send confirmation email to user
  6. Update Freshservice ticket status to "Completed"
- [ ] Configure error handling and rollback procedures
- [ ] Set up logging for audit trail
- [ ] Test workflow with sample request

**Workflow Logic**:
```yaml
Trigger: Service Catalogue Request Submitted
  - Catalogue Item: "[AppName] Access Request"

Step 1: Manager Approval
  - Send approval request to requester.manager
  - Timeout: 3 business days
  - On Timeout: Escalate to IT Manager

Step 2: Provisioning Actions (On Approval)
  - Action 2.1: Okta API - Add user to group
    - Endpoint: POST /api/v1/groups/{groupId}/users/{userId}
    - Group ID: From role mapping in custom object
    - User ID: From Okta user profile lookup

  - Action 2.2: Update Freshservice Custom Object
    - Object: [AppName]_Roles
    - Action: Add user to role assignment
    - Timestamp: Current datetime

  - Action 2.3: Update Trelica (if applicable)
    - API Call to Trelica to update user license

  - Action 2.4: Send Notification
    - To: Requester
    - CC: Manager, IT Admin
    - Template: "Access Granted - [AppName]"

Step 3: Error Handling
  - On Okta API Failure:
    - Log error to Freshservice notes
    - Send alert to IT provisioning team
    - Ticket status: "Requires Manual Intervention"

  - On Timeout:
    - Send reminder to approver
    - Escalate after 2 reminders

Step 4: Completion
  - Update ticket status: "Resolved"
  - Log all actions taken
  - Update audit log
```

---

## Phase 5: License Management Integration

### Step 5.1: Update Trelica
**Objective**: Sync application user data with license management system

**Actions**:
- [ ] Log into Trelica admin console
- [ ] Navigate to Applications → Add Application
- [ ] Search for application or add custom integration
- [ ] Configure application details:
  - Application name
  - License type (per-user, per-seat, unlimited)
  - Cost per license
  - Total licenses purchased
  - Renewal date
- [ ] Import current user assignments from Okta
- [ ] Set up automatic sync schedule (daily recommended)
- [ ] Configure cost allocation rules
- [ ] Set up license threshold alerts (e.g., 80% utilization)
- [ ] Verify data accuracy

**Trelica Configuration**:
```
Application Setup:
  - Name: [AppName]
  - Vendor: [Vendor Name]
  - License Model: Per User / Per Seat
  - Cost per License: $XX.XX
  - Total Licenses: XX
  - Contract Start Date: YYYY-MM-DD
  - Renewal Date: YYYY-MM-DD
  - Auto-renewal: Yes/No

Integration:
  - Sync Source: Okta Groups
  - Sync Frequency: Daily at 2:00 AM UTC
  - Sync Groups: [List of APP-[AppName]-* groups]

Alerts:
  - License Utilization > 80%: Email IT Finance
  - License Utilization > 95%: Email IT Finance + Procurement
  - Unused Licenses > 30 days: Weekly report to IT Manager
```

---

## Phase 6: Testing & Validation

### Step 6.1: Test SSO/SCIM with Test Account
**Objective**: Validate authentication and provisioning before user rollout

**Actions**:
- [ ] Create dedicated test user account in Okta: `test-sso@example.com`
- [ ] Assign test user to one of the new app groups
- [ ] Wait for SCIM sync (or trigger manual sync)
- [ ] Verify user provisioned in target application
- [ ] Test SSO login flow:
  - Navigate to app URL
  - Click "Sign in with SSO" or equivalent
  - Verify redirect to Okta
  - Verify successful authentication
  - Verify landing in application with correct role
- [ ] Test attribute mapping (name, email, role)
- [ ] Test group membership changes:
  - Remove user from group in Okta
  - Verify user deprovisioned or access revoked in app
  - Re-add user to group
  - Verify access restored
- [ ] Document any issues or unexpected behavior
- [ ] Test MFA enforcement if configured

**Test Checklist**:
- [ ] SSO login successful
- [ ] User profile attributes correctly mapped
- [ ] Role/permissions correctly assigned
- [ ] Group membership sync working
- [ ] Deprovision/revoke access working
- [ ] Re-provisioning working
- [ ] MFA enforced (if applicable)
- [ ] Session timeout configured correctly
- [ ] Logout function working

---

### Step 6.2: Add Seed Users to Groups
**Objective**: Provision initial set of real users for pilot testing

**Actions**:
- [ ] Identify 3-5 pilot users per role from RBAC sheet
- [ ] Confirm pilot participation with users and managers
- [ ] Add pilot users to appropriate Okta groups
- [ ] Monitor SCIM provisioning (typically 5-15 minutes)
- [ ] Verify users appear in application admin console
- [ ] Send onboarding instructions to pilot users
- [ ] Schedule 1:1 check-ins with pilot users
- [ ] Document feedback and issues

**Pilot User Criteria**:
- Technical proficiency (can provide detailed feedback)
- Available for testing during business hours
- Representative of different roles/use cases
- Willing to provide constructive feedback

---

### Step 6.3: Test Freshservice Catalogue & Provisioning
**Objective**: Validate end-to-end self-service access request workflow

**Actions**:
- [ ] Have test user submit access request through Freshservice catalogue
- [ ] Verify manager receives approval notification
- [ ] Approve request as manager
- [ ] Monitor workflow automation execution
- [ ] Verify Okta group assignment
- [ ] Verify SCIM provisioning to application
- [ ] Verify user receives confirmation email
- [ ] Verify Freshservice ticket updated correctly
- [ ] Test rejection workflow:
  - Submit request
  - Reject as manager
  - Verify no provisioning occurs
  - Verify rejection notification sent
- [ ] Document workflow timing and any bottlenecks

**Test Scenarios**:
1. **Happy Path**: Request → Approval → Provisioning → Success
2. **Rejection Path**: Request → Rejection → No Provisioning
3. **Timeout Path**: Request → No Response → Escalation
4. **Error Path**: Request → Approval → Provisioning Failure → Alert

---

## Phase 7: Communication & Rollout

### Step 7.1: Send Stakeholder Communications
**Objective**: Inform end users and teams about new SSO application availability

**Actions**:
- [ ] Prepare communication materials:
  - Announcement email
  - User guide/quick start
  - FAQ document
  - Support contact information
- [ ] Schedule rollout communications:
  - Initial announcement (1 week before go-live)
  - Go-live notification
  - Reminder email (1 week after go-live)
- [ ] Send communications to:
  - End users (based on RBAC sheet)
  - Team leads/managers
  - IT support team
  - Help desk team
- [ ] Create knowledge base article in Freshservice
- [ ] Update internal IT documentation
- [ ] Schedule optional training sessions or office hours

**Communication Template**:
```
Subject: New SSO Access Available: [AppName]

Hello Team,

We're excited to announce that [AppName] is now available with Single Sign-On (SSO) through Okta.

What This Means:
- Access [AppName] using your company credentials
- No separate password to remember
- Enhanced security through centralized authentication
- Easy access request process through IT Service Portal

How to Get Access:
1. Visit IT Service Portal: [URL]
2. Search for "[AppName] Access Request"
3. Select your required role
4. Provide business justification
5. Your manager will receive approval request
6. You'll receive access within 1 business day of approval

Resources:
- User Guide: [Link]
- FAQ: [Link]
- Support: it-support@example.com

Questions? Reply to this email or contact IT Support.

Best regards,
IT Team
```

---

### Step 7.2: Notify Global IT
**Objective**: Register new application in IT application inventory and support systems

**Actions**:
- [ ] Send notification to Global IT team
- [ ] Provide application details:
  - Application name and vendor
  - Purpose and business owner
  - SSO/SCIM enabled
  - Okta groups created
  - License count and cost
  - Support tier and escalation path
- [ ] Update IT application inventory/CMDB:
  - Application record
  - Integration details
  - Support documentation
  - Runbook links
- [ ] Add to IT monitoring systems (if applicable)
- [ ] Update IT support knowledge base
- [ ] Brief help desk team on common issues and troubleshooting
- [ ] Provide application overview to security team

**Global IT Notification Template**:
```
Subject: New SSO Application Live: [AppName]

Global IT Team,

[AppName] is now live with SSO/SCIM integration.

Application Details:
- Name: [AppName]
- Vendor: [Vendor Name]
- Business Owner: [Name, Email]
- IT Owner: [Name, Email]
- Purpose: [Brief description]
- Users: [Estimated user count]

Technical Details:
- SSO Protocol: SAML 2.0 / OIDC
- SCIM Version: 2.0
- Okta Groups: APP-[AppName]-*
- Freshservice Catalogue Item: [Link]
- Provisioning: Automated via workflow

Capabilities:
- Single Sign-On (SSO): Yes
- Automated Provisioning (SCIM): Yes
- Deprovisioning: Automated
- Self-Service Access Requests: Yes (Freshservice)
- License Management: Tracked in Trelica

Support Information:
- Tier 1: Help Desk (password resets, access requests)
- Tier 2: IT Provisioning Team (group assignments, workflow issues)
- Tier 3: IT Admin / Vendor Support (integration issues)
- Runbook: [Link to this document]

Documentation:
- User Guide: [Link]
- Admin Guide: [Link]
- Troubleshooting: [Link]
- Vendor Support: [Support Portal URL]

Please update CMDB and internal documentation accordingly.

Questions? Contact: [Your Name/Email]
```

---

## Phase 8: Post-Rollout & Monitoring

### Step 8.1: Monitor for Issues (First 2 Weeks)
**Actions**:
- [ ] Daily check of Freshservice tickets related to app
- [ ] Monitor Okta logs for authentication failures
- [ ] Review SCIM sync logs for provisioning errors
- [ ] Track license utilization in Trelica
- [ ] Collect user feedback
- [ ] Address issues promptly
- [ ] Update documentation based on common questions

---

### Step 8.2: Conduct Retrospective
**Actions**:
- [ ] Schedule retrospective meeting (2 weeks post-rollout)
- [ ] Review project timeline and blockers
- [ ] Identify process improvements
- [ ] Update this runbook with lessons learned
- [ ] Document edge cases and solutions
- [ ] Share findings with broader IT team

---

## Appendix

### A. Common Issues & Troubleshooting

**Issue**: SSO login fails with "User not found"
- **Cause**: User not provisioned via SCIM or email mismatch
- **Solution**: Verify SCIM sync completed, check email attribute mapping

**Issue**: User has access but wrong role/permissions
- **Cause**: Incorrect group assignment or role mapping
- **Solution**: Verify Okta group membership, check role mapping in custom object

**Issue**: Workflow automation fails
- **Cause**: API credentials expired, network issue, or API rate limit
- **Solution**: Check workflow logs, verify API credentials, check vendor API status

**Issue**: Manager approval not received
- **Cause**: Incorrect manager attribute in user profile
- **Solution**: Update user's manager field in Okta

---

### B. Rollback Procedures

If critical issues arise:
1. Disable SSO in application admin console
2. Revert to previous authentication method
3. Pause SCIM provisioning
4. Remove Freshservice catalogue item (temporarily)
5. Investigate and resolve issues
6. Re-enable components one at a time with testing

---

### C. Contact Information

- **IT Provisioning Team**: provisioning@example.com
- **Okta Admins**: okta-admins@example.com
- **Freshservice Support**: servicedesk@example.com
- **IT Security**: security@example.com
- **Global IT**: global-it@example.com

---

### D. Related Documentation

- [Okta SSO Configuration Standards]
- [Freshservice Workflow Automation Guide]
- [RBAC Template and Guidelines]
- [Trelica License Management Process]
- [IT Application Inventory]

---

**Document Version**: 1.0
**Last Updated**: 2026-01-13
**Owner**: IT Operations Team
**Review Cycle**: Quarterly
