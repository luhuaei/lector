;; -*- lexical-binding: t; -*-

(defcustom eaf-lector-extension-list
  '("epub")
  "The extension list of epub application."
  :type 'cons)

(add-to-list 'eaf-app-extensions-alist '("lector" . eaf-lector-extension-list))

(setq eaf-lector-module-path (concat (file-name-directory load-file-name) "buffer.py"))
(add-to-list 'eaf-app-module-path-alist '("lector" . eaf-lector-module-path))


(provide 'eaf-lector)
