# Leave Desk: supplied requirements

- L1: An end date before the start date must be rejected with a validation message, and no request should be created.
- L2: A request for more days than the remaining balance must be rejected with a validation message, and no request should be created.
- L3: The reason is optional and limited to 200 characters; a longer reason must be rejected with a validation message.
- L4: Cancelling a request requires confirmation; after confirming, the request shows status Cancelled and the dashboard's pending count decreases by one.
- L5: Saving an edit to a pending request must keep every field the user did not change, including the reason.
- L6: Profile changes, including the email-updates toggle, must still be shown after the page is reloaded.
- L7: Each status filter on My requests must show only requests with that status.
- L8: The team calendar must show only Pending and Approved requests, never Cancelled ones.
