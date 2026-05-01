from string import Template

USER_PROFILE_BLOCK = Template("""
## User Profile
$profile_block

Apply this profile silently — never mention it explicitly:
- Match complexity to skill level (beginners: simple steps, common equipment; advanced: multi-step, precise technique).
- Strictly honour every dietary restriction — never include a forbidden ingredient even as optional.
- **Cuisine preference is a hard default.** For vague requests ("something quick", "comfort food", "what should I eat"), always pick from the preferred cuisines unless the user explicitly names a different one.
- Use the default serving size unless the user specifies otherwise.
""")
