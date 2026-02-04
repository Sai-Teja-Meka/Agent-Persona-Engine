import React from 'react';

interface CardProps {
    children: React.ReactNode;
    className?: string;
    hover?: boolean;
    glass?: boolean;
    onClick?: () => void;
}

export function Card({
    children,
    className = '',
    hover,
    glass,
    onClick,
}: CardProps) {
    const baseStyles = 'rounded-xl p-6 border';
    const glassStyles = glass ? 'glass-effect' : 'bg-dark-900 border-dark-800';
    const hoverStyles = hover ? 'card-hover cursor-pointer' : '';

    return (
        <div
            className={`${baseStyles} ${glassStyles} ${hoverStyles} ${className}`}
            onClick={onClick}
        >
            {children}
        </div>
    );
}