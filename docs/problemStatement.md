# Problem Statement

## AI-Powered Restaurant Recommendation System (Zomato Use Case)

This project is an AI-powered restaurant recommendation service inspired by Zomato. The system suggests restaurants from a real-world dataset by combining structured filters with a Large Language Model (LLM), so recommendations are both relevant and explained in natural language.

All development for this project is in Python. That covers data loading and preprocessing, preference filtering, LLM integration, and the user-facing application.

## Objective

Design and implement a Python application that:

- Takes user preferences such as location, budget, cuisine, and ratings
- Uses a real-world dataset of restaurants
- Leverages an LLM to generate personalized, human-like recommendations
- Displays clear and useful results to the user

## Implementation

- Language: Python for every part of the system
- Scope: dataset handling, filtering, prompt construction, LLM calls, and result presentation

## System Workflow

### 1. Data Ingestion

- Load and preprocess the Zomato dataset from Hugging Face: [ManikaSaini/zomato-restaurant-recommendation](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation)
- Extract relevant fields such as restaurant name, location, cuisine, cost, and rating

### 2. User Input

Collect user preferences:

- **Location** — for example, Delhi or Bangalore
- **Budget** — low, medium, or high
- **Cuisine** — for example, Italian or Chinese
- **Minimum rating**
- **Additional preferences** — for example, family-friendly or quick service

### 3. Integration Layer

- Filter and prepare relevant restaurant data based on user input
- Pass structured results into an LLM prompt
- Design a prompt that helps the LLM reason about and rank options

### 4. Recommendation Engine

Use the LLM to:

- Rank restaurants
- Provide explanations for why each recommendation fits
- Optionally summarize the choices

### 5. Output Display

Present the top recommendations in a user-friendly format:

- Restaurant name
- Cuisine
- Rating
- Estimated cost
- AI-generated explanation

### 6. Health check

`GET /api/health`, served with the Streamlit page, reports whether the local restaurant cache can be read and whether an LLM API key is configured. It does not download the dataset and does not call the model.
