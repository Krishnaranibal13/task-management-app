pipeline {
    agent any

    stages {

        stage('Checkout') {
            steps {
                echo 'Checking out latest code...'
                checkout scm
            }
        }

        stage('Check Docker') {
            steps {
                sh '''
                    docker --version
                    docker compose version
                '''
            }
        }

        stage('Build Docker Images') {
            steps {
                echo 'Building Docker images...'
                sh '''
                    docker compose build
                '''
            }
        }

        stage('Deploy') {
            steps {
                echo 'Starting application...'
                sh '''
                    docker compose up -d
                '''
            }
        }

        stage('Verify Deployment') {
            steps {
                echo 'Checking containers...'
                sh '''
                    sleep 15
                    docker compose ps
                '''
            }
        }
    }

    post {
        success {
            echo '======================================'
            echo 'Task Management App deployed successfully!'
            echo '======================================'
        }

        failure {
            echo '======================================'
            echo 'Deployment failed!'
            echo 'Check Jenkins console logs.'
            echo '======================================'
        }
    }
}
