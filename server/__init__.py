"""
Anova Sous Vide Assistant Server Package.

This package contains the Flask API server for controlling
an Anova Precision Cooker via natural language commands from ChatGPT.

Main components:
- app: Flask application factory
- routes: HTTP endpoint handlers
- validators: Input validation and food safety enforcement
- anova_client: Anova Cloud API integration
- config: Configuration management
- middleware: Authentication and logging
- exceptions: Custom exception hierarchy
"""
