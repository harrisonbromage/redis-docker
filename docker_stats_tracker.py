import os
import requests
import logging
from datetime import datetime
import csv
from pathlib import Path
import subprocess
import json

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('docker_downloads.log'),
        logging.StreamHandler()
    ]
)

class DockerStatsTracker:
    def __init__(self):
        """Initialize the Docker Stats Tracker"""
        # Load projects configuration from environment variable
        self.projects = self._load_projects()
        
        # Directory to store download counts
        self.stats_dir = Path("stats")
        self.stats_dir.mkdir(exist_ok=True)
        
        # Combined CSV file for all repositories
        self.csv_file = self.stats_dir / "docker_downloads.csv"

    def _load_projects(self):
        """Load projects from DOCKER_PROJECTS environment variable"""
        projects_json = os.getenv('DOCKER_PROJECTS')
        if not projects_json:
            raise ValueError("DOCKER_PROJECTS environment variable is not set")
        
        try:
            projects = json.loads(projects_json)
            if not projects:
                raise ValueError("No projects defined in DOCKER_PROJECTS")
            return projects
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in DOCKER_PROJECTS: {str(e)}")

    def get_docker_downloads(self, username, repository):
        """Get the current download count from Docker Hub"""
        url = f"https://hub.docker.com/v2/repositories/{username}/{repository}/"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data['pull_count']
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch Docker Hub data for {username}/{repository}: {str(e)}")
            raise

    def store_data(self, date, downloads_data):
        """Save the download counts to a CSV file"""
        # Create CSV file with headers if it doesn't exist
        if not self.csv_file.exists():
            with open(self.csv_file, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["Date", "Repository", "Downloads"])
            logging.info("Created new CSV file for tracking downloads")
        
        # Add new data
        with open(self.csv_file, 'a', newline='') as file:
            writer = csv.writer(file)
            for repo_data in downloads_data:
                writer.writerow([
                    date,
                    f"{repo_data['username']}/{repo_data['repository']}",
                    repo_data['downloads']
                ])
        
        logging.info(f"Stored download counts for {len(downloads_data)} repositories")
        return self.csv_file

    def commit_and_push_changes(self, changed_file):
        """Commit and push changes to GitHub"""
        try:
            # Configure Git
            subprocess.run(['git', 'config', 'user.name', 'GitHub Actions Bot'])
            subprocess.run(['git', 'config', 'user.email', 'actions@github.com'])
            
            # Add file
            subprocess.run(['git', 'add', str(changed_file)])
            
            # Commit
            date = datetime.now().strftime("%Y-%m-%d")
            subprocess.run(['git', 'commit', '-m', f'Update download stats for {date}'])
            
            # Push
            subprocess.run(['git', 'push'])
            
            logging.info("Successfully committed and pushed changes to GitHub")
        except Exception as e:
            logging.error(f"Failed to commit and push changes: {str(e)}")
            raise

    def run(self):
        """Main method to run the tracker"""
        date = datetime.now().strftime("%Y-%m-%d")
        downloads_data = []
        errors = []

        # Collect data for all repositories
        for project in self.projects:
            try:
                username = project.get('username')
                repository = project.get('repository')
                
                if not username or not repository:
                    raise ValueError(f"Invalid project configuration: {project}")
                
                logging.info(f"Processing {username}/{repository}")
                downloads = self.get_docker_downloads(username, repository)
                
                downloads_data.append({
                    'username': username,
                    'repository': repository,
                    'downloads': downloads
                })
                
                # Print current stats
                print(f"\nDocker Hub Statistics for {username}/{repository}")
                print(f"Current Downloads: {downloads:,}")
                
            except Exception as e:
                error_msg = f"Error processing {username}/{repository}: {str(e)}"
                logging.error(error_msg)
                errors.append(error_msg)
                continue

        # Store all data if we have any successful fetches
        if downloads_data:
            csv_file = self.store_data(date, downloads_data)
            
            # If running in GitHub Actions, commit and push changes
            if os.getenv('GITHUB_ACTIONS'):
                try:
                    self.commit_and_push_changes(csv_file)
                except Exception as e:
                    errors.append(f"Failed to commit changes: {str(e)}")

        # If we had any errors, raise them at the end
        if errors:
            raise Exception("\n".join(errors))

        logging.info("Script completed successfully")

if __name__ == "__main__":
    try:
        tracker = DockerStatsTracker()
        tracker.run()
    except Exception as e:
        logging.error(f"Application error: {str(e)}")
        print(f"\nError: {str(e)}")
