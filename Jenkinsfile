pipeline {
    agent any

    environment {
        MYSQL_ROOT_PASSWORD = credentials('task-mysql-root-password')
        MYSQL_PASSWORD = credentials('task-mysql-password')
        MYSQL_DB = 'taskdb'
        MYSQL_USER = 'appuser'
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

        stage('Create Environment') {
            steps {
                sh '''
                    cat > .env <<EOF
MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}
MYSQL_PASSWORD=${MYSQL_PASSWORD}
MYSQL_DB=${MYSQL_DB}
MYSQL_USER=${MYSQL_USER}
MYSQL_HOST_PORT=33061
CORS_ALLOWED_ORIGINS_RAW=http://3.95.199.5
EOF

                    chmod 600 .env
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
                echo 'Deploying application...'
                sh '''
                    docker compose up -d
                '''
            }
        }

        stage('Verify Deployment') {
            steps {
                sh '''
                    sleep 15
                    docker compose ps
                '''
            }
        }
    }

    post {
        always {
            sh '''
                rm -f .env
            '''
        }

        success {
            echo 'Task Management App deployed successfully!'
        }

        failure {
            echo 'Deployment failed!'
        }
    }
}
