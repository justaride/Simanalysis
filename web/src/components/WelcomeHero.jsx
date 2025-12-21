import { motion } from 'framer-motion';
import { Microscope, Package, AlertTriangle, Sparkles, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

function WelcomeHero() {
    const navigate = useNavigate();

    const features = [
        {
            icon: Package,
            title: 'Scan Mods',
            description: 'Analyze your entire mod collection',
            color: 'blue',
        },
        {
            icon: AlertTriangle,
            title: 'Detect Conflicts',
            description: 'Find issues before they crash your game',
            color: 'orange',
        },
        {
            icon: Sparkles,
            title: 'Get Insights',
            description: 'Performance metrics and recommendations',
            color: 'purple',
        },
    ];

    const containerVariants = {
        hidden: { opacity: 0 },
        visible: {
            opacity: 1,
            transition: {
                staggerChildren: 0.1,
                delayChildren: 0.2,
            },
        },
    };

    const itemVariants = {
        hidden: { opacity: 0, y: 20 },
        visible: {
            opacity: 1,
            y: 0,
            transition: { duration: 0.5, ease: 'easeOut' },
        },
    };

    return (
        <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            className="flex flex-col items-center justify-center min-h-[600px] px-8"
        >
            {/* Hero Icon */}
            <motion.div
                variants={itemVariants}
                className="relative mb-8"
            >
                <div className="w-24 h-24 rounded-3xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-2xl shadow-blue-500/30 animate-glow">
                    <Microscope size={48} className="text-white" />
                </div>
                <motion.div
                    className="absolute -inset-4 bg-gradient-to-r from-blue-500/20 to-purple-500/20 rounded-full blur-xl -z-10"
                    animate={{
                        scale: [1, 1.1, 1],
                        opacity: [0.5, 0.8, 0.5],
                    }}
                    transition={{
                        duration: 3,
                        repeat: Infinity,
                        ease: 'easeInOut',
                    }}
                />
            </motion.div>

            {/* Title */}
            <motion.h1
                variants={itemVariants}
                className="text-4xl md:text-5xl font-bold text-center mb-4"
            >
                Welcome to{' '}
                <span className="gradient-text">Simanalysis</span>
            </motion.h1>

            {/* Subtitle */}
            <motion.p
                variants={itemVariants}
                className="text-gray-400 text-lg text-center max-w-lg mb-12"
            >
                Surgical analysis of your Sims 4 mods. Detect conflicts, find duplicates,
                and keep your game running smoothly.
            </motion.p>

            {/* Feature Cards */}
            <motion.div
                variants={itemVariants}
                className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12 w-full max-w-3xl"
            >
                {features.map((feature) => (
                    <motion.div
                        key={feature.title}
                        className="glass-card p-6 card-hover"
                        whileHover={{ scale: 1.02 }}
                        transition={{ type: 'spring', stiffness: 300 }}
                    >
                        <div className={`w-12 h-12 rounded-xl bg-${feature.color}-500/20 flex items-center justify-center mb-4`}>
                            <feature.icon size={24} className={`text-${feature.color}-400`} />
                        </div>
                        <h3 className="text-white font-semibold mb-2">{feature.title}</h3>
                        <p className="text-gray-400 text-sm">{feature.description}</p>
                    </motion.div>
                ))}
            </motion.div>

            {/* CTA Button */}
            <motion.button
                variants={itemVariants}
                onClick={() => navigate('/mods')}
                className="group flex items-center gap-3 px-8 py-4 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 text-white font-semibold rounded-2xl shadow-lg shadow-blue-500/25 transition-all duration-300"
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
            >
                <Package size={20} />
                Start Scanning
                <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
            </motion.button>

            {/* Tip */}
            <motion.p
                variants={itemVariants}
                className="text-gray-500 text-sm mt-6"
            >
                Tip: Point to your Mods folder to begin analysis
            </motion.p>
        </motion.div>
    );
}

export default WelcomeHero;
