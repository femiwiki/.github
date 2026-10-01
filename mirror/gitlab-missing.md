### `femiwiki/PATH` is missing on gitlab.com

```bash
glab api -X POST projects -F namespace_id="$(glab api groups/femiwiki | jq .id)" -f path=PATH -f name=PATH \
  -f description="Mirror of https://github.com/femiwiki/REPO" -f visibility=public \
  -f issues_access_level=disabled -f merge_requests_access_level=disabled \
  -f wiki_access_level=disabled -f snippets_access_level=disabled \
  -f builds_access_level=disabled -f pages_access_level=disabled >/dev/null
echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIB1C8EYC7ff52mZJJJDDn7U8FP9kD7H09E6Pr0wF9kvA femiwiki-gitlab-mirror' \
  | glab deploy-key add - -R femiwiki/PATH -t "GitHub Actions of femiwiki/.github" --can-push
```
