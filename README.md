# Album Recommendations
This repository contains a Streamlit web application that serves album recommendations from a personal music collection managed in a Notion database. It allows users to explore, filter, and discover music based on manually entered ratings.

## How It Works

The application uses the `notion-client` library to connect to the Notion API and fetch album data, including titles, artists, and ratings. This data is loaded into a pandas DataFrame and cached for performance using `st.cache_data`. The Streamlit framework provides the interactive web interface for users to interact with the data.

## Features

*   **Full Database View**: Display the entire collection of albums, sortable by rating.
*   **Filter by Rating**: Use a slider to filter albums by a minimum rating from 0 to 10.
*   **Filter by Artist**: Select an artist from a dropdown menu to see all albums by them in the database.
*   **Random Recommendation**: Get a random album suggestion from the collection (limited to albums with a rating of 7/10 or higher).

## Getting Started

You can run this application using GitHub Codespaces for a quick, pre-configured setup, or run it locally by following the manual setup instructions.

### With GitHub Codespaces (Recommended)

The easiest way to run this project is using GitHub Codespaces. The repository is pre-configured with a `.devcontainer` setup that automatically installs all dependencies and starts the Streamlit application for you.

1.  Click the **Code** button on the repository page.
2.  Select the **Codespaces** tab.
3.  Click **Create a codespace on main**.
4.  Once the codespace is built, the Streamlit application will automatically start and open in a new browser tab. You will still need to configure your Notion secrets as described in step 3 of the local setup.

### Local Setup

**1. Prerequisites**
*   Python 3.x
*   pip

**2. Clone the Repository**
```bash
git clone https://github.com/ChristianCrivelli/Album-Recommendations.git
cd Album-Recommendations
```

**3. Install Dependencies**
```bash
pip install -r requirements.txt
```

**4. Configure Notion Secrets**
This app requires a Notion API token and the ID of your Notion database to function.

1.  Create a directory named `.streamlit` in the root of the project:
    ```bash
    mkdir .streamlit
    ```
2.  Inside this directory, create a file named `secrets.toml`.
3.  Add your Notion credentials to the `secrets.toml` file in the following format. You can get your token by creating a new [Notion Integration](https://www.notion.so/my-integrations).

    ```toml
    # .streamlit/secrets.toml
    notion_albumdata_token = "YOUR_NOTION_API_TOKEN"
    notion_projects_id = "YOUR_NOTION_DATABASE_ID"
    ```

**5. Run the Application**
Once your dependencies are installed and secrets are configured, run the following command from the project's root directory:
```bash
streamlit run app.py
```
The application will be available at `http://localhost:8501`.
