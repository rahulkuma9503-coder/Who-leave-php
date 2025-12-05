# Use the official PHP-FPM image as a base
FROM php:8.2-fpm-alpine

# Install system dependencies and PHP extension build dependencies
RUN apk add --no-cache \
    nginx \
    supervisor \
    curl \
    oniguruma-dev \
    mariadb-dev

# Install PHP extensions required by the SDK
RUN docker-php-ext-install pdo pdo_mysql mbstring bcmath curl

# Install Composer
COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

# Set working directory
WORKDIR /var/www/html

# Copy project files
COPY . .

# Install PHP dependencies
RUN composer install --no-dev --optimize-autoloader

# Copy configuration files
COPY config/nginx.conf /etc/nginx/conf.d/default.conf
COPY config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create the data directory and set permissions
RUN mkdir -p data && chown -R www-data:www-data /var/www/html

# Expose port 8080 for Render
EXPOSE 8080

# Start supervisord to manage Nginx and PHP-FPM
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
