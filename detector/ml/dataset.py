"""Jeu d'exemples synthétique FR/EN pour entraîner le classifieur de fraude.

Ce n'est PAS un dataset réel : c'est un point de départ raisonnable pour faire
tourner le pipeline ML tant qu'aucune donnée de production n'est disponible.
Les schémas de fraude ci-dessous s'inspirent de patterns d'arnaque mobile
money/phishing largement documentés (blocage de compte, SIM swap, faux gain,
fausse mise à jour KYC, urgence familiale, fausse offre d'emploi).
À remplacer par de vrais SMS labellisés dès que possible (label=1 -> fraude).
"""

FRAUD_EXAMPLES = [
    # Blocage / réactivation de compte
    "Votre compte mobile money est bloqué, composez le *123# immediatement pour le reactiver",
    "URGENT: votre carte a ete bloquee. Composez *555# pour la reactiver immediatement",
    "Cher client votre compte sera suspendu, entrez votre code pin sur ce lien pour eviter le blocage",
    "Ceci est votre banque: composez le numero et donnez votre code pin pour debloquer le compte",
    "Suspicious activity on your account, verify immediately by dialing *999#",
    "Votre ligne sera coupee dans 24h, composez *100# et entrez votre code secret",
    "We noticed unusual login, confirm your pin code immediately or account gets blocked",
    "Cher abonne, votre compte mobile money va expirer, reactivez le en composant *144#",
    "FINAL NOTICE: dial *333# now and enter your secret code to avoid permanent blocking",
    "Your account has been blocked. Dial *123# immediately to reactivate",
    "URGENT: Your mobile money account is locked, send your PIN code to unlock now",
    "Votre compte a ete temporairement bloque pour securite, cliquez sur ce lien: bit.ly/verify-account",
    # SIM swap / changement de ligne
    "Alerte: une demande de changement de SIM a ete initiee, composez *144*1# pour l'annuler",
    "Your SIM card will be deactivated in 1 hour, dial *111# now to cancel the request",
    "Nous avons detecte une tentative de duplication de votre carte SIM, entrez votre code pin pour confirmer votre identite",
    # Faux gain / loterie
    "Felicitations vous avez gagne 500000 FCFA, envoyez votre code secret pour recevoir le gain",
    "Congratulations you won a prize, reply with your secret code to claim it",
    "Vous avez ete selectionne pour un cadeau de 1000 euros, composez *777# avant minuit pour le reclamer",
    "You have won a lottery of $2000, send your PIN code to our agent to receive the transfer",
    # Fausse mise a jour KYC / verification
    "Alerte securite: activite suspecte detectee, cliquez ici et confirmez votre code pin",
    "Votre dossier KYC doit etre mis a jour immediatement, cliquez ici et entrez votre code secret: bit.ly/kyc-update",
    "Your identity verification has expired, click http://bit.ly/x7z and enter your PIN to avoid suspension",
    "Mise a jour obligatoire de votre compte mobile money avant ce soir, composez *200# et confirmez votre code pin",
    # Urgence / faux colis / faux frais
    "Votre colis est bloque en douane, composez immediatement le *200# et payez les frais",
    "Cliquez ici http://192.168.1.1/login pour reactiver votre compte immediatement",
    "Your bank account is blocked, click http://bit.ly/x7z to verify your pin urgently",
    "Urgent besoin d'argent pour une urgence familiale, envoie ton code secret pour que je fasse le retrait a ta place",
    # Fausse offre d'emploi
    "Vous etes retenu pour un emploi bien paye, envoyez vos informations mobile money et code secret pour le contrat",
    "Congratulations, you are hired! Send your mobile money PIN to receive your first salary advance",
]

LEGITIMATE_EXAMPLES = [
    "Salut, on se voit toujours a 18h pour le foot ?",
    "Merci pour ton message, je te rappelle demain matin",
    "Ton colis Amazon arrivera entre 14h et 16h aujourd'hui",
    "Rappel: rendez-vous chez le dentiste jeudi a 10h",
    "Bonjour, la reunion de ce matin est reportee a 15h",
    "Hey, tu es dispo ce week-end pour un cafe ?",
    "Bonne fete de fin d'annee a toute la famille",
    "Le code de verification pour ta connexion est 482913",
    "Your OTP code for login is 738291, valid for 5 minutes",
    "Hi, are we still on for lunch tomorrow at noon?",
    "Your package has been delivered to your front door",
    "Reminder: your appointment is scheduled for Friday at 9am",
    "Merci d'avoir contacte notre service client, votre ticket est resolu",
    "Joyeux anniversaire, j'espere que tu passes une super journee",
    "La facture d'electricite de ce mois est disponible dans votre espace client",
    "Ton virement de 50 euros a bien ete recu, merci",
    "N'oublie pas d'acheter du pain en rentrant ce soir",
    "Le match de ce soir commence a 21h sur la chaine habituelle",
    "Ta commande a ete expediee, numero de suivi disponible dans l'application",
    "Merci d'avoir postule, nous reviendrons vers toi apres etude de ton dossier",
    "Ton abonnement a ete renouvele avec succes, bonne journee",
    "L'ecole sera fermee vendredi pour formation des enseignants",
    "On se retrouve devant le cinema a 20h comme prevu",
    "Ta reservation de restaurant est confirmee pour ce soir 19h30",
    "Le medecin te recois finalement a 11h au lieu de 10h",
    "Le solde de ton compte a ete mis a jour, consulte l'application pour le detail",
    "Merci pour ta candidature, un entretien te sera propose la semaine prochaine",
    "Ta facture de ce mois s'eleve a 45 euros, prelevement le 5",
]


def load_training_data():
    texts = FRAUD_EXAMPLES + LEGITIMATE_EXAMPLES
    labels = [1] * len(FRAUD_EXAMPLES) + [0] * len(LEGITIMATE_EXAMPLES)
    return texts, labels
