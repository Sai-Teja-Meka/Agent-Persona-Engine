import React from 'react';

interface BadgeProps {
    children: React.ReactNode;
    variant?: 'default' | 'primary' | 'success' | 'warning' | 'danger';
    size?: 'sm' | 'md';
}

export function Badge({
    children,
    variant = 'default',
    size = 'md',
}: BadgeProps) {
    const baseStyles = 'inline-flex items-center rounded-full font-medium';

    const variants = {
        default: 'bg-dark-800 text-dark-300',
        primary: 'bg-primary-500/10 text-primary-400',
        success: 'bg-green-500/10 text-green-400',
        warning: 'bg-yellow-500/10 text-yellow-400',
        danger: 'bg-red-500/10 text-red-400',
    };

    const sizes = {
        sm: 'px-2 py-0.5 text-xs',
        md: 'px-2.5 py-1 text-sm',
    };

    return (
        <span className={`${baseStyles} ${variants[variant]} ${sizes[size]}`}>
            {children}
        </span>
    );
}