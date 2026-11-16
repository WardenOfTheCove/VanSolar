# VanSolar

A solar forecast dashboard for Vancouver, Canada using NASA POWER data and a local linear regression model.

The app uses the NASA POWER API to get the solar radiation data for Vancouver, Canada and loads the All Sky Surface Shortwave Downward Radiance value. The data is then run through a Linear Regression Model that was trained on NASA POWER data from 1990-2010, then tested on data from 2010-2026.

The frontend is made with ReactJS and FastAPI gets the NASA POWER API data from the backend to the frontend. The frontend is themed with the shadcn/ui JS design system.

## Datasets

NASA POWER data on Vancouver, Canada from 1990-2010 for training the model

NASA POWER data on Vancouver, Canada from 2010-2026 for testing the trained model

NASA POWER API on Vancouver, Canada to get the latest data for more accurate results

## AI tools

Google Gemini used to understand and help with concepts for the linear regression model. Any code written by Gemini was usually removed, but useful bits were kept.

Copilot was used to make the frontend. Not as much editing, but primarily helped make the UI and structuring of the site.

The actual prediction model was mostly coded by me.


