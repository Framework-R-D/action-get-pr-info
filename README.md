# `action-get-pr-info`

> Retrieves PR information (ref, SHA, repo, base SHA) when triggered by an `issue_comment` event.

## Usage

```yaml
- uses: Framework-R-D/action-get-pr-info@v1  # pin to commit SHA in production
  with:
    input-name: value
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
