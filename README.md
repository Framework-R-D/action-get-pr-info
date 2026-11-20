# `action-get-pr-info`

> Retrieves PR information (ref, SHA, repo, base SHA) when triggered by an `issue_comment` event.

## Usage

```yaml
- uses: Framework-R-D/action-get-pr-info@25fa7302840aaf7330af010571bcd3c881a6770e # v2
```

## Inputs

| Name | Description | Required | Default |
|------|-------------|----------|---------|
(none)

## Outputs

| Name | Description |
|------|-------------|
| `ref` | The head ref of the PR |
| `sha` | The head SHA of the PR |
| `repo` | The full name of the head repository |
| `base_sha` | The SHA of the base branch |

## Metadata and approval

All outputs come from one validated PR API snapshot. Missing/deleted head repositories, malformed branch/repository values, and invalid or empty SHAs fail before output publication. `ref` remains the branch name, and `sha` remains the immutable head SHA. This resolver does not authorize reviewers, bind an approval to code, or establish the head at comment time. Privileged callers must separately authorize the exact repository and SHA and carry that snapshot through preparation, checkouts, artifacts, and push handling.

Policy and its tests use Python 3.12 or newer and the standard library. The small inline `github-script` step only performs the existing authenticated SDK request and writes its head/base metadata into an invocation-unique private runner-temporary file. Python validates that bounded regular-file snapshot before publishing outputs, then removes the metadata file. Python runs in isolated mode to ignore target-controlled import configuration. The other retained JavaScript step only adds the existing comment reaction; neither step owns snapshot policy, and no standalone Node test suite is required for this policy.

## License

[Apache 2.0](LICENSE)
