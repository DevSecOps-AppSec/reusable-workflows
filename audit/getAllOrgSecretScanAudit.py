import requests
import datetime
import csv
import argparse
import os

# Function to get all repositories in the organization
def get_all_repos(github_token, org_name):
    # GitHub API URL
    github_api_url = f"https://api.github.com/orgs/{org_name}/repos"

    # Headers for authentication
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json"
    }

    params = {
        'per_page': 100,  # Maximum number of repos per page
    }

    repo_list = []
    page = 1
    while True:
        # Get list of repos page by page
        params['page'] = page
        response = requests.get(github_api_url, headers=headers, params=params)

        if response.status_code != 200:
            print(f"Failed to fetch repos: {response.status_code} - {response.text}")
            break

        repos = response.json()
        if not repos:
            break

        # Collect repository data
        for repo in repos:
            creator = get_repo_creator(repo['full_name'], headers)
            has_pre_commit_config = check_pre_commit_config(repo['full_name'], headers)
            has_gitleaks_workflow = check_gitleaks_workflow(repo['full_name'], headers)
            custom_properties = get_repo_custom_properties(repo['full_name'], headers)  # Fetch "Repo_Type"
            branch_protection_enabled = check_branch_protection(repo['full_name'], repo['default_branch'], headers)
            repo_list.append({
                'name': repo['name'],
                'created_at': repo['created_at'],
                'creator': creator,
                'has_pre_commit_config': has_pre_commit_config,
                'has_gitleaks_workflow': has_gitleaks_workflow,
                'repo_type': custom_properties,
                'branch_protection_enabled': branch_protection_enabled
            })

        page += 1

    return repo_list

def compare_with_old_data(new_repo_list, old_file):
    if not os.path.exists(old_file):
        print(f"No previous data found. Creating new file '{old_file}'.")
        write_csv(old_file, new_repo_list)
        return
    
    # Read old data
    with open(old_file, mode='r') as file:
        reader = csv.DictReader(file)
        old_repo_list = list(reader)

    # Check if 'name' field exists in the CSV
    if not old_repo_list or 'Repo Name' not in old_repo_list[0]:
        print(f"CSV file does not contain the expected 'Repo Name' field. Please check the file format.")
        return
    
    # Convert old data to a dictionary for easy comparison
    old_repo_dict = {repo['Repo Name']: repo for repo in old_repo_list}
    
    # Check for new repos or changes in existing repos
    changes = []
    for new_repo in new_repo_list:
        old_repo = old_repo_dict.get(new_repo['name'])
        if not old_repo or old_repo != new_repo:
            changes.append(new_repo)
    
    if changes:
        print(f"Changes detected. Updating '{old_file}' with new data.")
        write_csv(old_file, new_repo_list)
    else:
        print("No changes detected.")

# Write repository data to CSV file
def write_csv(file_name, repo_list):
    with open(file_name, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Repo Name', 'Created At', 'Created By', 'Has .pre-commit-config.yaml', 'Has gitleaks_secret_scan.yml', 'Repo_Type', 'Branch Protection Enabled'])
        for repo in repo_list:
            writer.writerow([repo['name'], repo['created_at'], repo['creator'], repo['has_pre_commit_config'], repo['has_gitleaks_workflow'], repo['repo_type'], repo['branch_protection_enabled']])

# Function to get the creator of a repository
def get_repo_creator(repo_full_name, headers):
    events_url = f"https://api.github.com/repos/{repo_full_name}/events"
    response = requests.get(events_url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch events for {repo_full_name}: {response.status_code} - {response.text}")
        return "Unknown"

    events = response.json()
    for event in events:
        if event['type'] == 'CreateEvent':
            return event['actor']['login']
    return "Unknown"

# Function to check if .pre-commit-config.yaml exists in the repository
def check_pre_commit_config(repo_full_name, headers):
    contents_url = f"https://api.github.com/repos/{repo_full_name}/contents/.pre-commit-config.yaml"
    response = requests.get(contents_url, headers=headers)
    return response.status_code == 200

# Function to check if .github/workflows/gitleaks_secret_scan.yml exists in the repository
def check_gitleaks_workflow(repo_full_name, headers):
    workflow_url = f"https://api.github.com/repos/{repo_full_name}/contents/.github/workflows/gitleaks_secret_scan.yml"
    response = requests.get(workflow_url, headers=headers)
    return response.status_code == 200

# Function to get custom properties from a specific repository and return the "Repo_Type" value
def get_repo_custom_properties(repo_full_name, headers):
    custom_properties_url = f"https://api.github.com/repos/{repo_full_name}/properties/values"

    # Request custom properties from the repository
    response = requests.get(custom_properties_url, headers=headers)
    
    if response.status_code == 200:
        custom_properties = response.json()
        
        # Search for the "Repo_Type" property in the custom properties
        for prop in custom_properties:
            if prop['property_name'] == 'Repo_Type':
                return prop['value']  # Return the value of "Repo_Type"
        
        return 'Repo_Type not found'
    else:
        print(f"Failed to fetch custom properties for {repo_full_name}: {response.status_code} - {response.text}")
        return "Unknown"

# Function to check if branch protection is enabled for the default branch
def check_branch_protection(repo_full_name, default_branch, headers):
    protection_url = f"https://api.github.com/repos/{repo_full_name}/branches/{default_branch}/protection"
    response = requests.get(protection_url, headers=headers)
    
    if response.status_code == 200:
        return True  # Branch protection is enabled
    elif response.status_code == 404:
        return False  # Branch protection is not enabled
    else:
        print(f"Failed to check branch protection for {repo_full_name}: {response.status_code} - {response.text}")
        return "Unknown"

if __name__ == "__main__":
    # Parse command-line arguments for the GitHub token and organization name
    parser = argparse.ArgumentParser(description='Fetch all repositories and their custom properties, comparing them with old data.')
    parser.add_argument('-pat', '--github_token', type=str, required=True, help='GitHub Personal Access Token')
    parser.add_argument('-org', '--org_name', type=str, required=True, help='GitHub Organization Name')
    args = parser.parse_args()

    # Fetch all repositories
    all_repos = get_all_repos(args.github_token, args.org_name)

    # Compare with old data or create CSV if not present
    compare_with_old_data(all_repos, 'repos_data.csv')
    