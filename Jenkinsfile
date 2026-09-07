pipeline {
    agent any

    environment {
        APP_DIR = '/home/ubuntu/task-management-app'
    }

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
                    cd ${APP_DIR}
                    docker compose build
                '''
            }
        }

        stage('Stop Old Containers') {
            steps {
                echo 'Stopping old containers...'
                sh '''
                    cd ${APP_DIR}
                    docker compose down
                '''
            }
        }

        stage('Start Application') {
            steps {
                echo 'Starting application...'
                sh '''
                    cd ${APP_DIR}
                    docker compose up -d
                '''
            }
        }

        stage('Verify Deployment') {
            steps {
                echo 'Checking running containers...'
                sh '''
                    cd ${APP_DIR}
                    docker compose ps

                    echo "Waiting for application..."
                    sleep 15

                    docker compose ps
                '''
            }
        }
    }

    post {
        success {
            echo '======================================'
            echo 'Deployment successful!'
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
