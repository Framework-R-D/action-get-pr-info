# `action-get-pr-info`

> Retrieves PR information (ref, SHA, repo, base SHA) when triggered by an `issue_comment` event.

## Usage

```yaml
- uses: Framework-R-D/action-get-pr-info@e0d526cc97cfe9bbeff360a1b8be9679f32ec114 # v1
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
