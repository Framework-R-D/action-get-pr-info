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

## License

[Apache 2.0](LICENSE)
