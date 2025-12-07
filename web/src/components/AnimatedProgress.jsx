import { motion } from 'framer-motion';

function AnimatedProgress({ progress, status, size = 200 }) {
    const radius = size / 2 - 10;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = circumference - (progress / 100) * circumference;

    return (
        <div className="relative flex flex-col items-center justify-center" style={{ width: size, height: size }}>
            {/* Background Circle */}
            <svg
                className="absolute top-0 left-0 transform -rotate-90"
                width={size}
                height={size}
            >
                <circle
                    stroke="rgba(255, 255, 255, 0.1)"
                    strokeWidth="8"
                    fill="transparent"
                    r={radius}
                    cx={size / 2}
                    cy={size / 2}
                />
            </svg>

            {/* Progress Circle */}
            <svg
                className="absolute top-0 left-0 transform -rotate-90"
                width={size}
                height={size}
            >
                <motion.circle
                    stroke="#3b82f6"
                    strokeWidth="8"
                    fill="transparent"
                    r={radius}
                    cx={size / 2}
                    cy={size / 2}
                    strokeDasharray={circumference}
                    initial={{ strokeDashoffset: circumference }}
                    animate={{ strokeDashoffset }}
                    transition={{ duration: 0.5, ease: "easeInOut" }}
                    strokeLinecap="round"
                    style={{
                        filter: "drop-shadow(0 0 8px rgba(59, 130, 246, 0.5))"
                    }}
                />
            </svg>

            {/* Inner Content */}
            <div className="z-10 flex flex-col items-center text-center">
                <motion.div
                    initial={{ scale: 0.5, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    className="text-4xl font-bold text-white mb-1"
                >
                    {Math.round(progress)}%
                </motion.div>
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="text-xs text-blue-400 font-medium uppercase tracking-wider max-w-[150px] truncate px-2"
                >
                    {status || 'Processing...'}
                </motion.div>
            </div>

            {/* Pulsing Glow Effect */}
            <motion.div
                className="absolute inset-0 rounded-full bg-blue-500/10"
                animate={{
                    scale: [1, 1.1, 1],
                    opacity: [0.3, 0.1, 0.3],
                }}
                transition={{
                    duration: 2,
                    repeat: Infinity,
                    ease: "easeInOut"
                }}
            />
        </div>
    );
}

export default AnimatedProgress;
