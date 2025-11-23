# CI/CD Integration

Integrate Simanalysis into your continuous integration and deployment pipelines.

## Overview

Simanalysis can be integrated into CI/CD workflows to:

- Automatically detect conflicts when mods are added
- Enforce quality standards for mod collections
- Generate reports for review
- Alert on critical issues
- Track collection health over time

## GitHub Actions

### Example 1: Basic Workflow

Analyze mods on every push:

```yaml
# .github/workflows/analyze-mods.yml
name: Analyze Mods

on:
  push:
    branches: [main]
    paths:
      - 'mods/**'
  pull_request:
    branches: [main]
    paths:
      - 'mods/**'

jobs:
  analyze:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Simanalysis
        run: |
          python -m pip install --upgrade pip
          pip install simanalysis

      - name: Analyze mods
        run: |
          simanalysis analyze ./mods --output report.json --format json

      - name: Upload report
        uses: actions/upload-artifact@v3
        with:
          name: analysis-report
          path: report.json

      - name: Check for critical conflicts
        run: |
          critical=$(jq '[.conflicts[] | select(.severity == "CRITICAL")] | length' report.json)
          if [ $critical -gt 0 ]; then
            echo "❌ Found $critical critical conflicts"
            jq '.conflicts[] | select(.severity == "CRITICAL")' report.json
            exit 1
          fi
          echo "✅ No critical conflicts"
```

### Example 2: Multi-Platform Testing

Test on multiple operating systems:

```yaml
# .github/workflows/analyze-cross-platform.yml
name: Cross-Platform Analysis

on: [push, pull_request]

jobs:
  analyze:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ['3.9', '3.10', '3.11']

    runs-on: ${{ matrix.os }}

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install Simanalysis
        run: pip install simanalysis

      - name: Analyze mods
        run: |
          simanalysis analyze ./mods --output report_${{ matrix.os }}_py${{ matrix.python-version }}.json

      - name: Upload report
        uses: actions/upload-artifact@v3
        with:
          name: reports
          path: report_*.json
```

### Example 3: Scheduled Analysis

Run analysis on a schedule:

```yaml
# .github/workflows/scheduled-analysis.yml
name: Scheduled Mod Analysis

on:
  schedule:
    # Run every day at 2 AM UTC
    - cron: '0 2 * * *'
  workflow_dispatch:  # Allow manual trigger

jobs:
  analyze:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install simanalysis
          pip install requests  # For notification

      - name: Analyze mods
        run: |
          simanalysis analyze ./mods --output report.json

      - name: Compare with baseline
        id: compare
        run: |
          # Download previous report
          curl -H "Authorization: token ${{ secrets.GITHUB_TOKEN }}" \
               -o baseline.json \
               https://api.github.com/repos/${{ github.repository }}/actions/artifacts/latest

          # Compare conflict counts
          baseline_conflicts=$(jq '.conflicts | length' baseline.json || echo "0")
          current_conflicts=$(jq '.conflicts | length' report.json)

          echo "baseline=$baseline_conflicts" >> $GITHUB_OUTPUT
          echo "current=$current_conflicts" >> $GITHUB_OUTPUT
          echo "change=$((current_conflicts - baseline_conflicts))" >> $GITHUB_OUTPUT

      - name: Create issue if conflicts increased
        if: steps.compare.outputs.change > 0
        uses: actions/github-script@v6
        with:
          script: |
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: '⚠️ Mod Conflicts Increased',
              body: `Automated analysis detected an increase in conflicts:\n\n` +
                    `- Previous: ${{ steps.compare.outputs.baseline }}\n` +
                    `- Current: ${{ steps.compare.outputs.current }}\n` +
                    `- Change: +${{ steps.compare.outputs.change }}\n\n` +
                    `Review the latest analysis report for details.`,
              labels: ['mod-conflicts', 'automated']
            });

      - name: Upload report
        uses: actions/upload-artifact@v3
        with:
          name: daily-report-${{ github.run_number }}
          path: report.json
```

### Example 4: Pull Request Comments

Comment on PRs with analysis results:

```yaml
# .github/workflows/pr-analysis.yml
name: PR Mod Analysis

on:
  pull_request:
    paths:
      - 'mods/**'

jobs:
  analyze:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0  # Full history for comparison

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Simanalysis
        run: pip install simanalysis

      - name: Analyze current state
        run: |
          simanalysis analyze ./mods --output current.json

      - name: Analyze base branch
        run: |
          git checkout ${{ github.base_ref }}
          simanalysis analyze ./mods --output base.json
          git checkout ${{ github.head_ref }}

      - name: Generate comparison
        id: comparison
        run: |
          # Compare reports
          base_mods=$(jq '.mods | length' base.json)
          current_mods=$(jq '.mods | length' current.json)
          mods_change=$((current_mods - base_mods))

          base_conflicts=$(jq '.conflicts | length' base.json)
          current_conflicts=$(jq '.conflicts | length' current.json)
          conflicts_change=$((current_conflicts - base_conflicts))

          # Create summary
          cat > summary.md <<EOF
          ## 📊 Mod Analysis Report

          ### Changes
          - **Mods**: $base_mods → $current_mods ($mods_change)
          - **Conflicts**: $base_conflicts → $current_conflicts ($conflicts_change)

          ### Conflict Breakdown
          $(jq -r '.conflicts | group_by(.severity) | map("\(.length) \(.[0].severity)") | join(", ")' current.json)

          ### New Conflicts
          $(jq -r '.conflicts[] | select(.severity == "HIGH" or .severity == "CRITICAL") | "- [\(.severity)] \(.description)"' current.json | head -5)
          EOF

          echo "summary<<EOF" >> $GITHUB_OUTPUT
          cat summary.md >> $GITHUB_OUTPUT
          echo "EOF" >> $GITHUB_OUTPUT

      - name: Comment on PR
        uses: actions/github-script@v6
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `${{ steps.comparison.outputs.summary }}`
            });
```

## GitLab CI

### Example 5: Basic Pipeline

```yaml
# .gitlab-ci.yml
stages:
  - analyze
  - report

variables:
  MODS_DIR: "./mods"

analyze_mods:
  stage: analyze
  image: python:3.11
  before_script:
    - pip install simanalysis
  script:
    - simanalysis analyze $MODS_DIR --output report.json
    - |
      critical=$(jq '[.conflicts[] | select(.severity == "CRITICAL")] | length' report.json)
      if [ $critical -gt 0 ]; then
        echo "Critical conflicts found: $critical"
        exit 1
      fi
  artifacts:
    paths:
      - report.json
    expire_in: 1 week

generate_html_report:
  stage: report
  image: python:3.11
  dependencies:
    - analyze_mods
  script:
    - pip install jinja2
    - python generate_html_report.py report.json
  artifacts:
    paths:
      - report.html
    expire_in: 1 month
  only:
    - main
```

### Example 6: Docker-Based Pipeline

```yaml
# .gitlab-ci.yml
stages:
  - build
  - analyze

build_image:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker build -t simanalysis:latest .
    - docker tag simanalysis:latest $CI_REGISTRY_IMAGE:latest
    - docker push $CI_REGISTRY_IMAGE:latest
  only:
    - main

analyze_with_docker:
  stage: analyze
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker pull $CI_REGISTRY_IMAGE:latest
    - |
      docker run \
        -v $(pwd)/mods:/mods:ro \
        -v $(pwd)/output:/output \
        $CI_REGISTRY_IMAGE:latest \
        analyze /mods --output /output/report.json
  artifacts:
    paths:
      - output/report.json
```

## Jenkins

### Example 7: Jenkins Pipeline

```groovy
// Jenkinsfile
pipeline {
    agent any

    parameters {
        string(name: 'MODS_DIR', defaultValue: './mods', description: 'Mods directory')
        choice(name: 'SEVERITY_THRESHOLD', choices: ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'], description: 'Fail on severity')
    }

    stages {
        stage('Setup') {
            steps {
                sh 'pip install simanalysis'
            }
        }

        stage('Analyze') {
            steps {
                sh """
                    simanalysis analyze ${params.MODS_DIR} \
                        --output report.json \
                        --format json
                """
            }
        }

        stage('Check Conflicts') {
            steps {
                script {
                    def report = readJSON file: 'report.json'
                    def conflicts = report.conflicts

                    // Count by severity
                    def critical = conflicts.findAll { it.severity == 'CRITICAL' }.size()
                    def high = conflicts.findAll { it.severity == 'HIGH' }.size()

                    echo "Conflicts found:"
                    echo "  CRITICAL: ${critical}"
                    echo "  HIGH: ${high}"

                    // Fail based on threshold
                    if (params.SEVERITY_THRESHOLD == 'CRITICAL' && critical > 0) {
                        error("Critical conflicts detected")
                    } else if (params.SEVERITY_THRESHOLD == 'HIGH' && (critical + high) > 0) {
                        error("High or critical conflicts detected")
                    }
                }
            }
        }

        stage('Archive') {
            steps {
                archiveArtifacts artifacts: 'report.json', fingerprint: true
                publishHTML([
                    reportDir: '.',
                    reportFiles: 'report.html',
                    reportName: 'Mod Analysis Report'
                ])
            }
        }
    }

    post {
        always {
            emailext(
                subject: "Mod Analysis: ${currentBuild.result}",
                body: "Check ${env.BUILD_URL} for details",
                to: "${env.CHANGE_AUTHOR_EMAIL}"
            )
        }
    }
}
```

## CircleCI

### Example 8: CircleCI Configuration

```yaml
# .circleci/config.yml
version: 2.1

orbs:
  python: circleci/python@2.1.1

jobs:
  analyze:
    docker:
      - image: cimg/python:3.11
    steps:
      - checkout

      - python/install-packages:
          pkg-manager: pip
          pip-dependency-file: requirements.txt

      - run:
          name: Install Simanalysis
          command: pip install simanalysis

      - run:
          name: Analyze mods
          command: |
            simanalysis analyze ./mods --output report.json

      - run:
          name: Check for critical conflicts
          command: |
            critical=$(jq '[.conflicts[] | select(.severity == "CRITICAL")] | length' report.json)
            if [ $critical -gt 0 ]; then
              echo "Found $critical critical conflicts"
              jq '.conflicts[] | select(.severity == "CRITICAL")' report.json
              exit 1
            fi

      - store_artifacts:
          path: report.json

      - store_test_results:
          path: test-results

workflows:
  analyze-mods:
    jobs:
      - analyze:
          filters:
            branches:
              only:
                - main
                - develop
```

## Travis CI

### Example 9: Travis Configuration

```yaml
# .travis.yml
language: python
python:
  - "3.9"
  - "3.10"
  - "3.11"

install:
  - pip install simanalysis

script:
  - simanalysis analyze ./mods --output report.json
  - |
    critical=$(jq '[.conflicts[] | select(.severity == "CRITICAL")] | length' report.json)
    if [ $critical -gt 0 ]; then
      echo "Critical conflicts found"
      exit 1
    fi

after_success:
  - bash <(curl -s https://codecov.io/bash)

deploy:
  provider: releases
  api_key: $GITHUB_TOKEN
  file: report.json
  skip_cleanup: true
  on:
    tags: true
```

## Custom Scripts

### Example 10: Pre-Commit Hook

Analyze mods before committing:

```bash
#!/bin/bash
# .git/hooks/pre-commit

echo "Analyzing mods before commit..."

# Analyze only staged mod files
staged_mods=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(package|ts4script)$')

if [ -z "$staged_mods" ]; then
    echo "No mod files changed"
    exit 0
fi

# Create temporary directory for staged files
temp_dir=$(mktemp -d)

for mod in $staged_mods; do
    mkdir -p "$temp_dir/$(dirname $mod)"
    git show ":$mod" > "$temp_dir/$mod"
done

# Analyze
simanalysis analyze "$temp_dir" --quiet --output /tmp/pre_commit_report.json

# Check for critical conflicts
critical=$(jq '[.conflicts[] | select(.severity == "CRITICAL")] | length' /tmp/pre_commit_report.json)

# Cleanup
rm -rf "$temp_dir"

if [ $critical -gt 0 ]; then
    echo "❌ Cannot commit: Found $critical critical conflicts"
    jq '.conflicts[] | select(.severity == "CRITICAL")' /tmp/pre_commit_report.json
    echo ""
    echo "Fix conflicts or use 'git commit --no-verify' to bypass"
    exit 1
fi

echo "✅ No critical conflicts detected"
exit 0
```

**Install hook:**
```bash
chmod +x .git/hooks/pre-commit
```

### Example 11: Automated Report Deployment

Deploy reports to GitHub Pages:

```bash
#!/bin/bash
# deploy_reports.sh

# Analyze mods
simanalysis analyze ./mods --output report.json

# Generate HTML report
python generate_html_report.py report.json > report.html

# Create GitHub Pages structure
mkdir -p gh-pages
cp report.html gh-pages/index.html
cp report.json gh-pages/report.json

# Add timestamp
echo "Last updated: $(date)" > gh-pages/last_updated.txt

# Deploy to GitHub Pages
cd gh-pages
git init
git add .
git commit -m "Update mod analysis report"
git push -f https://github.com/username/mod-reports.git main:gh-pages

echo "Report deployed to: https://username.github.io/mod-reports/"
```

## Docker Compose for CI

### Example 12: CI with Docker Compose

```yaml
# docker-compose.ci.yml
version: '3.8'

services:
  analyzer:
    build: .
    volumes:
      - ./mods:/mods:ro
      - ./output:/output
    command: analyze /mods --output /output/report.json
    environment:
      - LOG_LEVEL=INFO

  reporter:
    image: python:3.11
    depends_on:
      - analyzer
    volumes:
      - ./output:/output
    command: >
      bash -c "
        pip install jinja2 &&
        python /scripts/generate_report.py /output/report.json
      "

  notifier:
    image: curlimages/curl
    depends_on:
      - reporter
    volumes:
      - ./output:/output
    command: >
      sh -c "
        curl -X POST $WEBHOOK_URL \
          -H 'Content-Type: application/json' \
          -d @/output/notification.json
      "
```

**Run CI pipeline:**
```bash
docker-compose -f docker-compose.ci.yml up --abort-on-container-exit
```

## Monitoring and Alerting

### Example 13: Slack Notifications

Send analysis results to Slack:

```python
# notify_slack.py
import json
import os
import requests
from pathlib import Path

def send_slack_notification(report_path: Path, webhook_url: str):
    """Send analysis report to Slack."""
    with open(report_path) as f:
        report = json.load(f)

    total_mods = len(report['mods'])
    total_conflicts = len(report['conflicts'])

    # Count by severity
    severity_counts = {}
    for conflict in report['conflicts']:
        severity = conflict['severity']
        severity_counts[severity] = severity_counts.get(severity, 0) + 1

    # Build message
    emoji = "✅" if total_conflicts == 0 else "⚠️"
    color = "good" if total_conflicts == 0 else "warning"

    if severity_counts.get('CRITICAL', 0) > 0:
        emoji = "❌"
        color = "danger"

    message = {
        "text": f"{emoji} Mod Analysis Complete",
        "attachments": [
            {
                "color": color,
                "fields": [
                    {
                        "title": "Total Mods",
                        "value": str(total_mods),
                        "short": True
                    },
                    {
                        "title": "Total Conflicts",
                        "value": str(total_conflicts),
                        "short": True
                    },
                ],
            }
        ],
    }

    # Add severity breakdown if conflicts exist
    if severity_counts:
        severity_text = "\n".join(
            f"{severity}: {count}"
            for severity, count in severity_counts.items()
        )
        message["attachments"][0]["fields"].append({
            "title": "By Severity",
            "value": severity_text,
            "short": False
        })

    # Send to Slack
    response = requests.post(webhook_url, json=message)
    response.raise_for_status()
    print("Notification sent to Slack")


if __name__ == "__main__":
    report_path = Path("report.json")
    webhook_url = os.environ["SLACK_WEBHOOK_URL"]

    send_slack_notification(report_path, webhook_url)
```

**Use in CI:**
```yaml
- name: Notify Slack
  run: python notify_slack.py
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### Example 14: Email Reports

Send detailed reports via email:

```python
# email_report.py
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

def send_email_report(report_path: Path, to_email: str):
    """Send analysis report via email."""
    with open(report_path) as f:
        report = json.load(f)

    # Generate HTML report
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            .critical {{ color: red; font-weight: bold; }}
            .high {{ color: orange; font-weight: bold; }}
            .medium {{ color: #FFD700; }}
            .low {{ color: green; }}
        </style>
    </head>
    <body>
        <h1>Mod Analysis Report</h1>
        <p><strong>Total Mods:</strong> {len(report['mods'])}</p>
        <p><strong>Total Conflicts:</strong> {len(report['conflicts'])}</p>

        <h2>Conflicts</h2>
        <ul>
    """

    for conflict in report['conflicts'][:10]:  # First 10 conflicts
        severity_class = conflict['severity'].lower()
        html += f"""
            <li class="{severity_class}">
                [{conflict['severity']}] {conflict['description']}
            </li>
        """

    html += """
        </ul>
        <p><em>Full report attached</em></p>
    </body>
    </html>
    """

    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Mod Analysis Report - {len(report['conflicts'])} conflicts"
    msg['From'] = "noreply@simanalysis.com"
    msg['To'] = to_email

    msg.attach(MIMEText(html, 'html'))

    # Send email
    with smtplib.SMTP('localhost') as server:
        server.send_message(msg)

    print(f"Report emailed to {to_email}")


if __name__ == "__main__":
    import sys
    send_email_report(Path("report.json"), sys.argv[1])
```

## Best Practices

### 1. Cache Dependencies

Speed up CI runs by caching Python packages:

```yaml
- name: Cache pip packages
  uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
```

### 2. Fail Fast on Critical Issues

Exit immediately on critical conflicts:

```bash
critical=$(jq '[.conflicts[] | select(.severity == "CRITICAL")] | length' report.json)
[ $critical -gt 0 ] && exit 1 || exit 0
```

### 3. Archive Reports

Keep historical reports for tracking:

```yaml
- name: Archive report
  uses: actions/upload-artifact@v3
  with:
    name: report-${{ github.run_number }}
    path: report.json
    retention-days: 90
```

### 4. Use Matrix Builds

Test across multiple environments:

```yaml
strategy:
  matrix:
    python: ['3.9', '3.10', '3.11']
    os: [ubuntu, windows, macos]
```

### 5. Implement Quality Gates

Define clear pass/fail criteria:

```python
def check_quality_gate(report: dict) -> bool:
    """Check if mod collection passes quality gate."""
    conflicts = report['conflicts']

    # No critical conflicts allowed
    if any(c['severity'] == 'CRITICAL' for c in conflicts):
        return False

    # Max 5 high-severity conflicts
    high_count = sum(1 for c in conflicts if c['severity'] == 'HIGH')
    if high_count > 5:
        return False

    return True
```

## Next Steps

- Review [Basic Examples](basic.md) for fundamentals
- Explore [Advanced Examples](advanced.md) for custom implementations
- Read [User Guide](../user-guide/analyzing-mods.md) for detailed documentation
- Check [GitHub Actions Marketplace](https://github.com/marketplace) for ready-made actions

---

**Version**: 3.0.0 | **Last Updated**: 2025-11-23
